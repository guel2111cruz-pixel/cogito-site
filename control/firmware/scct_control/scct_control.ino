// STANDALONE REFERENCE — no original camera firmware was supplied.
// This sketch controls the demo AP only. It does NOT initialize a camera.
// Merge with an existing camera sketch only after reviewing its Wi-Fi/UART use.
#include <WiFi.h>
#include <Preferences.h>

// Replace locally with SCCT_DEVICE_KEY. NEVER commit the filled-in key.
const char* CONTROL_KEY = "REPLACE_WITH_64_HEX_CHARACTERS";
const char* SSID = "COGITO-DEMO";
const char* PASSWORDS[] = {"12345678", "password", "qwerty12", "cogito26"};
Preferences prefs;
String line;
String lastID;
int activeChoice = 0;
bool apReady = false;
bool storageReady = false;
bool dropping = false;

bool authorized(const String& supplied) {
  if (strlen(CONTROL_KEY) != 64 || supplied.length() != 64) return false;
  unsigned char difference = 0;
  for (size_t i = 0; i < 64; i++) difference |= supplied[i] ^ CONTROL_KEY[i];
  return difference == 0;
}
bool validID(const String& id) {
  if (id.length() != 36) return false;
  for (int i = 0; i < 36; i++) {
    if (i == 8 || i == 13 || i == 18 || i == 23) { if (id[i] != '-') return false; }
    else if (!((id[i] >= '0' && id[i] <= '9') || (id[i] >= 'a' && id[i] <= 'f'))) return false;
  }
  return true;
}
void processLine(const String& input) {
  if (!input.startsWith("SET ")) return;
  int first = input.indexOf(' ', 4), second = input.indexOf(' ', first + 1);
  if (first < 0 || second < 0) return;
  String id = input.substring(4, first);
  String choice = input.substring(first + 1, second);
  if (!validID(id)) return;
  if (!authorized(input.substring(second + 1))) { Serial.println("ERROR " + id + " AUTH"); return; }
  if (!storageReady) { Serial.println("ERROR " + id + " STORAGE"); return; }
  if (choice.length() != 1 || choice[0] < '0' || choice[0] > '3') { Serial.println("ERROR " + id + " CHOICE"); return; }
  int selected = choice[0] - '0';
  if (id == lastID && selected != activeChoice) { Serial.println("ERROR " + id + " CONFLICT"); return; }
  if (id == lastID && apReady) { Serial.println("APPLIED " + id); return; }
  WiFi.softAPdisconnect(true); // All demo AP clients disconnect here.
  delay(250);
  WiFi.mode(WIFI_AP);
  apReady = WiFi.softAP(SSID, PASSWORDS[selected]);
  if (!apReady) { Serial.println("ERROR " + id + " AP"); return; }
  // One durable record keeps id and password choice consistent across power loss.
  String record = id + " " + String(selected);
  if (prefs.putString("ap-record", record) == 0) { Serial.println("ERROR " + id + " STORAGE"); return; }
  lastID = id;
  activeChoice = selected;
  Serial.println("APPLIED " + id); // Sent only after softAP succeeds and record persists.
}
void setup() {
  Serial.begin(115200);
  line.reserve(180);
  storageReady = prefs.begin("scct", false);
  String record = storageReady ? prefs.getString("ap-record", "") : "";
  if (record.length() == 38 && validID(record.substring(0, 36)) && record[37] >= '0' && record[37] <= '3') {
    lastID = record.substring(0, 36);
    activeChoice = record[37] - '0';
  }
  WiFi.mode(WIFI_AP);
  apReady = WiFi.softAP(SSID, PASSWORDS[activeChoice]);
  Serial.println(apReady ? "READY" : "ERROR BOOT AP");
}
void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      if (!dropping) processLine(line);
      line = ""; dropping = false;
    } else if (c != '\r' && !dropping) {
      if (line.length() < 180) line += c;
      else { line = ""; dropping = true; }
    }
  }
  delay(1);
}
