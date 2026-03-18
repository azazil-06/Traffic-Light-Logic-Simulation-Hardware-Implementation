// ================= PIN DEFINITIONS =================
// POST 1
#define P1_RED     12
#define P1_YELLOW  11
#define P1_GREEN   10

// POST 2
#define P2_RED     9
#define P2_YELLOW  8
#define P2_GREEN   7

// TIMEOUT SAFETY (Lights turn off if PC disconnects)
unsigned long lastCmdTime = 0;
const long TIMEOUT_MS = 1500; 

void setup() {
  // Configure Pins
  pinMode(P1_RED, OUTPUT); pinMode(P1_YELLOW, OUTPUT); pinMode(P1_GREEN, OUTPUT);
  pinMode(P2_RED, OUTPUT); pinMode(P2_YELLOW, OUTPUT); pinMode(P2_GREEN, OUTPUT);

  Serial.begin(9600);
  turnAllOff(); // Start in OFF state
}

void loop() {
  // 1. Check if PC sent a command
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    lastCmdTime = millis(); // Reset "Keep Alive" timer
    executeCommand(cmd);
  }

  // 2. Safety Check: If no data from PC for 1.5 seconds, SHUT DOWN
  if (millis() - lastCmdTime > TIMEOUT_MS) {
    turnAllOff();
  }
}

// Function to handle PC orders
void executeCommand(char cmd) {
  // 'A' = Phase 1 (Green/Red)
  // 'B' = Phase 2 (Yellow/Red)
  // 'C' = Phase 3 (Red/Green)
  // 'D' = Phase 4 (Red/Yellow)
  
  if (cmd == 'A') setLights(LOW, LOW, HIGH, HIGH, LOW, LOW);
  else if (cmd == 'B') setLights(LOW, HIGH, LOW, HIGH, LOW, LOW);
  else if (cmd == 'C') setLights(HIGH, LOW, LOW, LOW, LOW, HIGH);
  else if (cmd == 'D') setLights(HIGH, LOW, LOW, LOW, HIGH, LOW);
}

void setLights(bool p1r, bool p1y, bool p1g, bool p2r, bool p2y, bool p2g) {
  digitalWrite(P1_RED, p1r); digitalWrite(P1_YELLOW, p1y); digitalWrite(P1_GREEN, p1g);
  digitalWrite(P2_RED, p2r); digitalWrite(P2_YELLOW, p2y); digitalWrite(P2_GREEN, p2g);
}

void turnAllOff() {
  setLights(LOW, LOW, LOW, LOW, LOW, LOW);
}

