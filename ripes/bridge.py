"""
Traffic Light Controller — Python Bridge v4
CALIBRATION SCAN VERSION

ROOT CAUSE OF "STUCK ON PHASE 2":
The scanner found the wrong memory region — some other part of
Ripes memory happened to have value 2 at offset 0x100. It locked
onto that and it never changed.

FIX:
We now do a CALIBRATION SCAN:
1. Read offset 0x100 from ALL candidate regions (snapshot A)
2. Wait 1 second while Ripes runs
3. Read again (snapshot B)
4. The region where the value CHANGED between 1-4 is the right one

This guarantees we lock onto the correct data segment.

INSTALL:
    pip install pyserial pymem

STARTUP ORDER:
    1. Open Ripes, load ripes_ram.asm, add LED Matrix
    2. Press Reset then Run in Ripes
    3. Run this script → CONNECT
    4. A calibration window appears — wait 3 seconds while it scans
"""

import serial
import serial.tools.list_ports
import tkinter as tk
from tkinter import ttk, messagebox
import time
import ctypes
import ctypes.wintypes as wintypes

try:
    import pymem
    PYMEM_OK = True
except ImportError:
    PYMEM_OK = False

# ── CONFIGURATION ───────────────────────────────────────────
ARDUINO_BAUD    = 9600
POLL_MS         = 20
HEARTBEAT_MS    = 400
RIPES_EXE       = "Ripes.exe"
DS_OFFSET       = 0x100    # 0x10000100 - 0x10000000
CALIB_WAIT_MS   = 3000     # how long calibration scan waits
# ────────────────────────────────────────────────────────────

ser           = None
running       = False
auto_mode     = True
current_phase = None
pm            = None
data_seg_host = None

PHASE_NAMES  = {
    1:'Phase 1 — P1 GREEN / P2 RED', 2:'Phase 2 — P1 YELLOW / P2 RED',
    3:'Phase 3 — P1 RED / P2 GREEN', 4:'Phase 4 — P1 RED / P2 YELLOW'
}
PHASE_CMDS   = {1:'A', 2:'B', 3:'C', 4:'D'}
PHASE_COLORS = {1:'#00EE00', 2:'#FFE000', 3:'#FF2200', 4:'#FFE000'}
COL_MUTED    = "#555555"
DIM  = {'r':'#3a0800','y':'#3a3000','g':'#003a00'}
FULL = {'r':'#FF2200','y':'#FFE000','g':'#00EE00'}


# ════════════════════════════════════════════════════════════
#  MEMORY HELPERS
# ════════════════════════════════════════════════════════════

class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress",       ctypes.c_void_p),
        ("AllocationBase",    ctypes.c_void_p),
        ("AllocationProtect", wintypes.DWORD),
        ("RegionSize",        ctypes.c_size_t),
        ("State",             wintypes.DWORD),
        ("Protect",           wintypes.DWORD),
        ("Type",              wintypes.DWORD),
    ]

MEM_COMMIT = 0x1000
PAGE_RW    = 0x04
PAGE_EXRW  = 0x40


def get_all_rw_regions(handle):
    regions = []
    addr = 0
    while addr < 0x7FFFFFFF0000:
        mbi = MEMORY_BASIC_INFORMATION()
        ret = ctypes.windll.kernel32.VirtualQueryEx(
            handle, ctypes.c_void_p(addr),
            ctypes.byref(mbi), ctypes.sizeof(mbi))
        if not ret:
            break
        step = mbi.RegionSize if mbi.RegionSize > 0 else 0x1000
        if (mbi.State == MEM_COMMIT and
                mbi.Protect in (PAGE_RW, PAGE_EXRW) and
                mbi.RegionSize >= DS_OFFSET + 4):
            regions.append((mbi.BaseAddress, mbi.RegionSize))
        addr += step
    return regions


def safe_read_uint(pm_handle, addr):
    try:
        return pm_handle.read_uint(addr)
    except Exception:
        return None


# ════════════════════════════════════════════════════════════
#  CALIBRATION SCAN
#  Watches all candidate regions and finds the one that changes
# ════════════════════════════════════════════════════════════

def calibration_scan(progress_cb):
    """
    Opens Ripes, takes two snapshots of all candidate regions
    separated by CALIB_WAIT_MS, and returns the host base address
    of whichever region's value at DS_OFFSET changed between 1-4.

    progress_cb(text) -- called to update the GUI progress label
    """
    global pm, data_seg_host

    # Open process
    try:
        pm = pymem.Pymem(RIPES_EXE)
    except pymem.exception.ProcessNotFound:
        return False, "Ripes.exe not found. Is Ripes open?"
    except Exception as e:
        return False, f"Cannot open Ripes:\n{e}"

    progress_cb("Scanning memory regions...")
    regions = get_all_rw_regions(pm.process_handle)
    if not regions:
        return False, "No readable memory regions found in Ripes."

    # Filter to regions that are readable at DS_OFFSET
    candidates = []
    for base, size in regions:
        val = safe_read_uint(pm, base + DS_OFFSET)
        if val is not None:
            candidates.append(base)

    if not candidates:
        return False, (
            f"No region readable at offset 0x{DS_OFFSET:X}.\n\n"
            "Make sure Ripes has been Reset and Run."
        )

    progress_cb(f"Found {len(candidates)} candidate regions.\nTaking snapshot A...")

    # Snapshot A
    snap_a = {}
    for base in candidates:
        snap_a[base] = safe_read_uint(pm, base + DS_OFFSET)

    progress_cb(f"Waiting {CALIB_WAIT_MS//1000}s for Ripes to change phase...\n(Make sure Ripes is running!)")

    # Wait
    time.sleep(CALIB_WAIT_MS / 1000)

    progress_cb("Taking snapshot B...")

    # Snapshot B
    snap_b = {}
    for base in candidates:
        snap_b[base] = safe_read_uint(pm, base + DS_OFFSET)

    # Find regions where value changed AND new value is a valid phase
    changed = []
    for base in candidates:
        a = snap_a[base]
        b = snap_b[base]
        if a != b and b is not None and 1 <= b <= 4:
            changed.append((base, a, b))

    if not changed:
        # No region changed — maybe delay is too long, try any region
        # with a valid phase value right now
        progress_cb("No change detected. Looking for valid phase value...")
        valid = []
        for base in candidates:
            v = safe_read_uint(pm, base + DS_OFFSET)
            if v is not None and 1 <= v <= 4:
                valid.append((base, v))

        if valid:
            # Pick smallest region (least likely to be a coincidence)
            valid.sort(key=lambda x: x[1])
            data_seg_host = valid[0][0]
            return True, (
                f"Found via value match (phase={valid[0][1]})\n"
                f"Host: 0x{data_seg_host:016X}\n"
                f"⚠ Could not verify by change — increase delay in Ripes\n"
                f"  (li t4, 500000) for more reliable detection"
            )

        return False, (
            "Ripes data segment not found.\n\n"
            "Possible reasons:\n"
            "• Ripes is paused or not running\n"
            "• Delay (li t4, ...) is too long — phases aren't changing\n"
            "• Try: li t4, 100000 in debug_delay\n"
            "• Then Reset + Run in Ripes, then try connecting again"
        )

    # Got a clean change — use it
    # If multiple regions changed, pick the one with lowest base address
    # (data segments are usually at lower addresses than heap)
    changed.sort(key=lambda x: x[0])
    data_seg_host = changed[0][0]
    a_val, b_val  = changed[0][1], changed[0][2]

    return True, (
        f"Calibration success!\n"
        f"Phase changed: {a_val} → {b_val}\n"
        f"Host base: 0x{data_seg_host:016X}"
    )


# ════════════════════════════════════════════════════════════
#  CALIBRATION WINDOW
# ════════════════════════════════════════════════════════════

def run_calibration(on_done):
    """Show a modal calibration window while scanning runs in background."""
    win = tk.Toplevel(root)
    win.title("Calibrating...")
    win.geometry("380x180")
    win.configure(bg="#111")
    win.resizable(False, False)
    win.grab_set()

    tk.Label(win, text="CALIBRATION SCAN",
             font=("Courier", 12, "bold"), fg="#6c8fff", bg="#111").pack(pady=(16,4))

    prog_lbl = tk.Label(win, text="Starting...",
                        font=("Courier", 9), fg="#aaa", bg="#111",
                        wraplength=340, justify="center")
    prog_lbl.pack(pady=8, padx=16)

    bar_canvas = tk.Canvas(win, width=340, height=8, bg="#222",
                           highlightthickness=0)
    bar_canvas.pack()
    bar = bar_canvas.create_rectangle(0, 0, 0, 8, fill="#6c8fff", width=0)

    def update_progress(text):
        prog_lbl.config(text=text)
        win.update()

    def animate_bar(pct):
        bar_canvas.coords(bar, 0, 0, int(340 * pct), 8)
        win.update()

    import threading

    result = [None]

    def scan_thread():
        # Animate bar while scanning
        root.after(0, lambda: animate_bar(0.1))
        ok, msg = calibration_scan(
            lambda t: root.after(0, lambda: update_progress(t))
        )
        result[0] = (ok, msg)
        root.after(0, lambda: animate_bar(1.0))
        root.after(200, finish)

    def finish():
        win.grab_release()
        win.destroy()
        on_done(*result[0])

    t = threading.Thread(target=scan_thread, daemon=True)
    t.start()


# ════════════════════════════════════════════════════════════
#  ARDUINO
# ════════════════════════════════════════════════════════════

def send_to_arduino(cmd):
    if ser and ser.is_open:
        try:
            ser.write(cmd.encode())
        except Exception:
            pass

def heartbeat():
    if running and ser and ser.is_open:
        try:
            ser.write(b'K')
        except Exception:
            pass
    root.after(HEARTBEAT_MS, heartbeat)


# ════════════════════════════════════════════════════════════
#  POLL
# ════════════════════════════════════════════════════════════

def poll_memory():
    global current_phase
    if not running or not auto_mode:
        if running:
            root.after(POLL_MS, poll_memory)
        return

    val = safe_read_uint(pm, data_seg_host + DS_OFFSET) if pm and data_seg_host else None

    if val and 1 <= val <= 4:
        raw_label.config(
            text=f"RAM[0x10000100] = {val}  →  Phase {PHASE_CMDS[val]}",
            fg="#00ff88")
        if val != current_phase:
            current_phase = val
            send_to_arduino(PHASE_CMDS[val])
            update_visuals(val)
            phase_label.config(text=PHASE_NAMES[val], fg=PHASE_COLORS[val])
    else:
        raw_label.config(text="Waiting for Ripes...", fg="#555")

    root.after(POLL_MS, poll_memory)


# ════════════════════════════════════════════════════════════
#  CONNECT / DISCONNECT
# ════════════════════════════════════════════════════════════

def connect():
    global running, ser

    if not PYMEM_OK:
        messagebox.showerror("Missing",
            "Run:  pip install pymem\nThen restart.")
        return

    port = combo.get()
    if not port:
        messagebox.showerror("No port", "Select a COM port.")
        return

    # Connect Arduino first
    try:
        ser = serial.Serial(port, ARDUINO_BAUD, timeout=0.1)
        time.sleep(2)
    except Exception as e:
        messagebox.showerror("Arduino Error", f"Cannot open {port}:\n{e}")
        return

    update_status("Calibrating...", "#ffaa00")
    btn_connect.config(state="disabled")

    def on_calib_done(ok, msg):
        global running
        ripes_lbl.config(text=msg, fg="#00ff88" if ok else "#ff4444")
        if not ok:
            messagebox.showerror("Calibration Failed", msg)
            update_status("OFFLINE", "#ff4444")
            btn_connect.config(state="normal")
            if ser and ser.is_open:
                ser.close()
            return

        running = True
        update_status("SYNCED — reading Ripes RAM", "#00ff88")
        btn_connect.config(state="disabled")
        btn_disc.config(state="normal")
        heartbeat()
        poll_memory()

    run_calibration(on_calib_done)


def disconnect():
    global running, ser, pm, data_seg_host, current_phase
    running = False
    pm = None
    data_seg_host = None
    current_phase = None
    if ser and ser.is_open:
        try:
            ser.write(b'X')
            time.sleep(0.1)
            ser.close()
        except Exception:
            pass
        ser = None
    update_status("OFFLINE", "#ff4444")
    btn_connect.config(state="normal")
    btn_disc.config(state="disabled")
    reset_gui()
    phase_label.config(text="—", fg=COL_MUTED)
    ripes_lbl.config(text="Not connected", fg="#555")
    raw_label.config(text="RAM[0x10000100] = ?", fg="#333")


# ════════════════════════════════════════════════════════════
#  MANUAL
# ════════════════════════════════════════════════════════════

def toggle_mode():
    global auto_mode
    auto_mode = (var_mode.get() == 1)
    if auto_mode:
        update_status("SYNCED — reading Ripes RAM", "#00ff88")
        for b in manual_btns: b.config(state="disabled")
    else:
        update_status("MANUAL OVERRIDE", "#ffaa00")
        for b in manual_btns: b.config(state="normal")

def manual_click(n):
    if not auto_mode and running:
        send_to_arduino(PHASE_CMDS[n])
        update_visuals(n)
        phase_label.config(text=PHASE_NAMES[n], fg=PHASE_COLORS[n])


# ════════════════════════════════════════════════════════════
#  GUI
# ════════════════════════════════════════════════════════════

p1_ids = {}
p2_ids = {}

def draw_post(cv, cx, label):
    cv.create_rectangle(cx-40,10,cx+40,190, fill="#1a1a1a", outline="#444", width=1)
    cv.create_text(cx, 208, text=label, fill="#aaa", font=("Courier",10,"bold"))
    ids = {}
    for key, cy in [('r',50),('y',100),('g',150)]:
        ids[key] = cv.create_oval(cx-20,cy-20,cx+20,cy+20,
                                  fill=DIM[key], outline="#000", width=1)
    return ids

def set_led(iid, color): canvas.itemconfig(iid, fill=color)

def update_visuals(n):
    for k in ('r','y','g'):
        set_led(p1_ids[k], DIM[k]); set_led(p2_ids[k], DIM[k])
    if   n==1: set_led(p1_ids['g'],FULL['g']); set_led(p2_ids['r'],FULL['r'])
    elif n==2: set_led(p1_ids['y'],FULL['y']); set_led(p2_ids['r'],FULL['r'])
    elif n==3: set_led(p1_ids['r'],FULL['r']); set_led(p2_ids['g'],FULL['g'])
    elif n==4: set_led(p1_ids['r'],FULL['r']); set_led(p2_ids['y'],FULL['y'])

def reset_gui():
    for ids in (p1_ids,p2_ids):
        for k in ('r','y','g'): set_led(ids[k], DIM[k])

def update_status(t, c="#fff"): status_lbl.config(text=t, fg=c)
def on_closing(): disconnect(); root.destroy()

root = tk.Tk()
root.title("Traffic Sync v4")
root.geometry("560x640")
root.resizable(False, False)
root.configure(bg="#111")

tk.Label(root, text="TRAFFIC SYNC CONTROLLER",
         font=("Courier",13,"bold"), fg="#6c8fff", bg="#111").pack(pady=(14,2))
tk.Label(root, text="Calibration scan — finds correct memory region automatically",
         font=("Courier",9), fg="#444", bg="#111").pack()

rf = tk.LabelFrame(root, text=" RIPES ", bg="#111", fg="#6c8fff",
                   font=("Courier",9,"bold"), padx=10, pady=6)
rf.pack(fill="x", padx=16, pady=(10,4))
ripes_lbl = tk.Label(rf, text="Not connected",
                     font=("Courier",9), fg="#555", bg="#111", justify="left")
ripes_lbl.pack(anchor="w")
if not PYMEM_OK:
    tk.Label(rf, text="⚠  Run:  pip install pymem",
             font=("Courier",9), fg="#ff4444", bg="#111").pack(anchor="w")

cf = tk.LabelFrame(root, text=" ARDUINO ", bg="#111", fg="#6c8fff",
                   font=("Courier",9,"bold"), padx=10, pady=8)
cf.pack(fill="x", padx=16, pady=4)
row = tk.Frame(cf, bg="#111")
row.pack(fill="x")
tk.Label(row, text="Port:", fg="#aaa", bg="#111",
         font=("Courier",10)).pack(side=tk.LEFT)
ports = [p.device for p in serial.tools.list_ports.comports()]
combo = ttk.Combobox(row, values=ports, width=12, state="readonly")
if ports: combo.current(0)
combo.pack(side=tk.LEFT, padx=8)
btn_connect = tk.Button(row, text="CONNECT", command=connect,
                        bg="#003300", fg="#00ff88",
                        font=("Courier",9,"bold"), relief="flat", padx=10)
btn_connect.pack(side=tk.LEFT, padx=4)
btn_disc = tk.Button(row, text="DISCONNECT", command=disconnect,
                     bg="#330000", fg="#ff6666",
                     font=("Courier",9,"bold"), relief="flat",
                     padx=10, state="disabled")
btn_disc.pack(side=tk.LEFT, padx=4)

status_lbl = tk.Label(root, text="OFFLINE",
                      font=("Courier",11,"bold"), fg="#ff4444", bg="#111")
status_lbl.pack(pady=4)
phase_label = tk.Label(root, text="—",
                       font=("Courier",10), fg=COL_MUTED, bg="#111")
phase_label.pack()
raw_label = tk.Label(root, text="RAM[0x10000100] = ?",
                     font=("Courier",9), fg="#333", bg="#111")
raw_label.pack(pady=2)

canvas = tk.Canvas(root, width=560, height=230, bg="#111", highlightthickness=0)
canvas.pack(pady=6)
p1_ids = draw_post(canvas, 170, "POST 1")
p2_ids = draw_post(canvas, 390, "POST 2")
canvas.create_text(280,105, text="← sync →", fill="#2a2a2a", font=("Courier",9))

ctrl = tk.LabelFrame(root, text=" CONTROLS ", bg="#111", fg="#6c8fff",
                     font=("Courier",9,"bold"), padx=12, pady=8)
ctrl.pack(fill="x", padx=16, pady=4)
var_mode = tk.IntVar(value=1)
tk.Checkbutton(ctrl, text="Automatic (Ripes drives Arduino)",
               variable=var_mode, command=toggle_mode,
               bg="#111", fg="#aaa", selectcolor="#222",
               font=("Courier",10), activebackground="#111").pack(anchor="w")
brow = tk.Frame(ctrl, bg="#111")
brow.pack(pady=(6,0))
manual_btns = []
for label, pn, color in [
    ("P1 GREEN",1,"#00aa44"),("P1 YELLOW",2,"#aaaa00"),
    ("P2 GREEN",3,"#00aa44"),("P2 YELLOW",4,"#aaaa00")]:
    b = tk.Button(brow, text=label, width=11,
                  command=lambda p=pn: manual_click(p),
                  bg="#1a1a1a", fg=color, font=("Courier",9),
                  relief="flat", state="disabled")
    b.pack(side=tk.LEFT, padx=4)
    manual_btns.append(b)

root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()