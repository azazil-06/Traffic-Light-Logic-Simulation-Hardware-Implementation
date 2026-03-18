import serial
import serial.tools.list_ports
import tkinter as tk
from tkinter import ttk, messagebox
import random

# ================== GLOBAL STATE ==================
ser = None
running = False
auto_mode = True
disco_mode = False
current_phase = 'A'

# ================== LOGIC: SEND & SYNC ==================
def send_cmd(cmd):
    global current_phase
    current_phase = cmd
    if ser and ser.is_open:
        try:
            ser.write(cmd.encode())
        except:
            pass

def heartbeat():
    """ Keeps Arduino alive; paused during Disco to prevent signal lag """
    if running and ser and ser.is_open and not disco_mode:
        send_cmd(current_phase)
    root.after(500, heartbeat)

def update_visuals(phase):
    if phase == 'A': # P1 Green, P2 Red
        set_gui_lights(p1_lights, "#400000", "#404000", "#00FF00")
        set_gui_lights(p2_lights, "#FF0000", "#404000", "#004000")
    elif phase == 'B': # P1 Yellow, P2 Red
        set_gui_lights(p1_lights, "#400000", "#FFFF00", "#004000")
        set_gui_lights(p2_lights, "#FF0000", "#404000", "#004000")
    elif phase == 'C': # P1 Red, P2 Green
        set_gui_lights(p1_lights, "#FF0000", "#404000", "#004000")
        set_gui_lights(p2_lights, "#400000", "#404000", "#00FF00")
    elif phase == 'D': # P1 Red, P2 Yellow
        set_gui_lights(p1_lights, "#FF0000", "#404000", "#004000")
        set_gui_lights(p2_lights, "#400000", "#FFFF00", "#004000")

def set_gui_lights(lights, r, y, g):
    canvas.itemconfig(lights[0], fill=r)
    canvas.itemconfig(lights[1], fill=y)
    canvas.itemconfig(lights[2], fill=g)

# ================== MODES: DISCO & AUTO ==================
def run_disco():
    if not disco_mode or not running: return
    
    # Chaos: Random phases and background flashes
    random_phase = random.choice(['A', 'B', 'C', 'D'])
    send_cmd(random_phase)
    update_visuals(random_phase)
    
    flash_colors = ["#1e1e1e", "#4b0082", "#000000", "#2e0854"]
    root.configure(bg=random.choice(flash_colors))
    
    root.after(120, run_disco) # High speed (120ms)

def run_phase(phase):
    if not running or not auto_mode or disco_mode: return
    
    send_cmd(phase)
    update_visuals(phase)
    
    # Cycle Timings
    next_phase = 'A'
    delay = 2000
    if phase == 'A': next_phase = 'B'; delay = 4000 # P1 Green Time
    elif phase == 'B': next_phase = 'C'; delay = 2000 # P1 Transition
    elif phase == 'C': next_phase = 'D'; delay = 4000 # P2 Green Time
    elif phase == 'D': next_phase = 'A'; delay = 2000 # P2 Transition
        
    root.after(delay, lambda: run_phase(next_phase))

# ================== GUI ACTIONS ==================
def connect():
    global ser, running
    try:
        port = combo.get()
        if not port: 
            messagebox.showwarning("Warning", "Please select a COM port")
            return
        ser = serial.Serial(port, 9600, timeout=0.1)
        running = True
        status_lbl.config(text="SYSTEM ONLINE", fg="#00ff00")
        heartbeat() 
        if auto_mode: run_phase('A')
    except Exception as e:
        messagebox.showerror("Error", f"Connection Failed: {e}")

def toggle_mode():
    global auto_mode, disco_mode
    disco_mode = False 
    root.configure(bg="#1e1e1e")
    if var_mode.get() == 1:
        auto_mode = True
        status_lbl.config(text="SYSTEM ONLINE - AUTOMATIC", fg="#00ff00")
        disable_buttons()
        run_phase(current_phase)
    else:
        auto_mode = False
        status_lbl.config(text="MANUAL OVERRIDE ACTIVE", fg="orange")
        enable_buttons()

def toggle_disco():
    global disco_mode
    if not running:
        messagebox.showinfo("Connect First", "Please connect to the Arduino before starting the party.")
        return
    
    disco_mode = not disco_mode
    if disco_mode:
        status_lbl.config(text="DISCO MODE ACTIVE! 🕺", fg="#ff00ff")
        run_disco()
    else:
        root.configure(bg="#1e1e1e")
        toggle_mode()

def manual_click(phase):
    if not auto_mode and not disco_mode:
        send_cmd(phase)
        update_visuals(phase)

# ================== WINDOW SETUP ==================
root = tk.Tk()
root.title("Traffic Control Center - COM7 Disco")
root.geometry("520x620")
root.configure(bg="#1e1e1e")

# Port Selection with COM7 Priority
top_frame = tk.Frame(root, bg="#1e1e1e", pady=10)
top_frame.pack()

tk.Label(top_frame, text="COM Port:", fg="white", bg="#1e1e1e").pack(side=tk.LEFT)
ports = [p.device for p in serial.tools.list_ports.comports()]
if "COM7" not in ports:
    ports.append("COM7")

combo = ttk.Combobox(top_frame, values=ports, state="readonly", width=10)
combo.set("COM7")
combo.pack(side=tk.LEFT, padx=5)

btn_connect = tk.Button(top_frame, text="CONNECT", command=connect, bg="#005500", fg="white", font=("Arial", 9, "bold"))
btn_connect.pack(side=tk.LEFT, padx=10)

status_lbl = tk.Label(root, text="STATUS: OFFLINE", fg="#ff0000", bg="#1e1e1e", font=("Courier", 12, "bold"))
status_lbl.pack()

# Visualization
canvas = tk.Canvas(root, width=520, height=220, bg="#1e1e1e", highlightthickness=0)
canvas.pack()

def draw_signal(x, label):
    canvas.create_rectangle(x-35, 20, x+35, 170, fill="#2b2b2b", outline="#555")
    canvas.create_text(x, 190, text=label, fill="white", font=("Arial", 10, "bold"))
    r = canvas.create_oval(x-16, 40-16, x+16, 40+16, fill="#400000")
    y = canvas.create_oval(x-16, 90-16, x+16, 90+16, fill="#404000")
    g = canvas.create_oval(x-16, 140-16, x+16, 140+16, fill="#004000")
    return r, y, g

p1_lights = draw_signal(170, "POST 1 (N/S)")
p2_lights = draw_signal(350, "POST 2 (E/W)")

# Controls
control_frame = tk.LabelFrame(root, text="CONTROLS", bg="#1e1e1e", fg="orange", padx=10, pady=10)
control_frame.pack(pady=5, fill="x", padx=20)

var_mode = tk.IntVar(value=1)
chk_auto = tk.Checkbutton(control_frame, text="Enable Automatic Mode", variable=var_mode, command=toggle_mode, bg="#1e1e1e", fg="white", selectcolor="#333")
chk_auto.pack()

btn_frame = tk.Frame(control_frame, bg="#1e1e1e")
btn_frame.pack()

b1 = tk.Button(btn_frame, text="P1 GREEN", width=12, command=lambda: manual_click('A'))
b2 = tk.Button(btn_frame, text="P1 YELLOW", width=12, command=lambda: manual_click('B'))
b3 = tk.Button(btn_frame, text="P2 GREEN", width=12, command=lambda: manual_click('C'))
b4 = tk.Button(btn_frame, text="P2 YELLOW", width=12, command=lambda: manual_click('D'))

b1.grid(row=0, column=0, padx=5, pady=5); b2.grid(row=0, column=1, padx=5, pady=5)
b3.grid(row=1, column=0, padx=5, pady=5); b4.grid(row=1, column=1, padx=5, pady=5)

disco_btn = tk.Button(root, text="TOGGLE DISCO MODE 🕺", command=toggle_disco, bg="#800080", fg="white", font=("Arial", 10, "bold"), height=2)
disco_btn.pack(pady=10, fill="x", padx=30)

def disable_buttons():
    for b in [b1, b2, b3, b4]: b.config(state="disabled")
def enable_buttons():
    for b in [b1, b2, b3, b4]: b.config(state="normal")

disable_buttons()

def on_closing():
    global running
    running = False
    if ser and ser.is_open:
        ser.close()
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()