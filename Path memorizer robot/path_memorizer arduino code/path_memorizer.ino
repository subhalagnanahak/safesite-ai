#include <IRremote.h>

// Motor Pins
const int IN1 = 2;
const int IN2 = 3;
const int IN3 = 4;
const int IN4 = 5;

// IR receiver pin
const int RECV_PIN = 11;

// Define IR remote buttons (32-bit values from Serial Monitor)
#define FORWARD_BUTTON  0xF609FD02
#define BACKWARD_BUTTON 0xEE11FD02
#define LEFT_BUTTON     0xF30CFD02
#define RIGHT_BUTTON    0xF10EFD02
#define RECORD_BUTTON   0xF906FD02  //  button for starting/stopping recording
#define REPEAT_BUTTON   0xFE01FD02  //  button for replaying recorded path

// Direction constants
#define DIR_FORWARD  'F'
#define DIR_BACKWARD 'B'
#define DIR_LEFT     'L'
#define DIR_RIGHT    'R'
#define DIR_STOP     'S'

// Structure to store movement data
struct Movement {
  char direction;
  unsigned long duration;
};

// Array to store the recorded path (max 50 movements)
Movement recordedPath[50];
int pathIndex = 0;                    // Current index in recordedPath
bool isRecording = false;             // Recording state
char currentDirection = DIR_STOP;     // Current direction of the robot
unsigned long lastCommandTime = 0;    // Time of the last received command
unsigned long movementStartTime = 0;  // Time when the current movement started
const int DEBOUNCE_DELAY = 200;       // Minimum delay between commands in milliseconds
const int MOVEMENT_DURATION = 3000;   // Duration of movement in milliseconds (3 seconds)

void setup() {
  // Initialize motor control pins as outputs
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);
  
  // Stop motors initially
  stopMotors();
  
  // Initialize IR receiver
  IrReceiver.begin(RECV_PIN, ENABLE_LED_FEEDBACK);
  
  // Start serial communication for debugging
  Serial.begin(9600);
  Serial.println("IR Robot Controller with Path Recording Ready");
}

void loop() {
  // Check for IR signal
  if (IrReceiver.decode()) {
    unsigned long receivedCode = IrReceiver.decodedIRData.decodedRawData;
    
    // Debug print
    Serial.print("Button: 0x");
    Serial.println(receivedCode, HEX);
    
    // Process command if it's new or if enough time has passed since last command
    unsigned long currentTime = millis();
    if (currentTime - lastCommandTime > DEBOUNCE_DELAY) {
      lastCommandTime = currentTime;
      
      // Process the received command
      switch (receivedCode) {
        case FORWARD_BUTTON:
          currentDirection = DIR_FORWARD;
          movementStartTime = currentTime;
          moveForward();
          if (isRecording && pathIndex < 50) {
            recordedPath[pathIndex] = {DIR_FORWARD, MOVEMENT_DURATION};
            pathIndex++;
          }
          Serial.println("Moving Forward for 3 seconds");
          break;
          
        case BACKWARD_BUTTON:
          currentDirection = DIR_BACKWARD;
          movementStartTime = currentTime;
          moveBackward();
          if (isRecording && pathIndex < 50) {
            recordedPath[pathIndex] = {DIR_BACKWARD, MOVEMENT_DURATION};
            pathIndex++;
          }
          Serial.println("Moving Backward for 3 seconds");
          break;
          
        case LEFT_BUTTON:
          turnLeft();
          delay(300);
          stopMotors();
          if (isRecording && pathIndex < 50) {
            recordedPath[pathIndex] = {DIR_LEFT, 300};
            pathIndex++;
          }
          currentDirection = DIR_STOP;
          Serial.println("Quick Turn Left");
          break;
          
        case RIGHT_BUTTON:
          turnRight();
          delay(300);
          stopMotors();
          if (isRecording && pathIndex < 50) {
            recordedPath[pathIndex] = {DIR_RIGHT, 300};
            pathIndex++;
          }
          currentDirection = DIR_STOP;
          Serial.println("Quick Turn Right");
          break;
          
        case RECORD_BUTTON:
          if (!isRecording) {
            // Start recording
            isRecording = true;
            pathIndex = 0;  // Reset path
            Serial.println("Recording started");
          } else {
            // Stop recording
            isRecording = false;
            Serial.print("Recording stopped. ");
            Serial.print(pathIndex);
            Serial.println(" movements recorded.");
          }
          break;
          
        case REPEAT_BUTTON:
          if (!isRecording) {
            Serial.println("Replaying recorded path");
            replayPath();
          }
          break;
          
        default:
          // Unknown command - do nothing
          break;
      }
    }
    
    // Resume receiving
    IrReceiver.resume();
  }
  
  // Check if it's time to stop a timed movement (only for forward and backward)
  if (currentDirection == DIR_FORWARD || currentDirection == DIR_BACKWARD) {
    unsigned long currentTime = millis();
    if (currentTime - movementStartTime >= MOVEMENT_DURATION) {
      currentDirection = DIR_STOP;
      stopMotors();
      Serial.println("Movement time completed - stopping");
    }
  }
  
  // Maintain the current direction
  maintainDirection();
}

// Function to replay the recorded path
void replayPath() {
  for (int i = 0; i < pathIndex; i++) {
    switch (recordedPath[i].direction) {
      case DIR_FORWARD:
        moveForward();
        Serial.println("Replay: Moving Forward");
        break;
      case DIR_BACKWARD:
        moveBackward();
        Serial.println("Replay: Moving Backward");
        break;
      case DIR_LEFT:
        turnLeft();
        Serial.println("Replay: Turning Left");
        break;
      case DIR_RIGHT:
        turnRight();
        Serial.println("Replay: Turning Right");
        break;
    }
    delay(recordedPath[i].duration);
    stopMotors();
  }
  Serial.println("Replay completed");
}

// Function to maintain the current direction
void maintainDirection() {
  switch (currentDirection) {
    case DIR_FORWARD:
      moveForward();
      break;
    case DIR_BACKWARD:
      moveBackward();
      break;
    case DIR_LEFT:
      turnLeft();
      break;
    case DIR_RIGHT:
      turnRight();
      break;
    case DIR_STOP:
    default:
      stopMotors();
      break;
  }
}

void moveForward() {
  digitalWrite(IN1, HIGH);
  digitalWrite(IN2, LOW);
  digitalWrite(IN3, HIGH);
  digitalWrite(IN4, LOW);
}

void moveBackward() {
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, HIGH);
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, HIGH);
}

void turnLeft() {
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, HIGH);
  digitalWrite(IN3, HIGH);
  digitalWrite(IN4, LOW);
}

void turnRight() {
  digitalWrite(IN1, HIGH);
  digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, HIGH);
}

void stopMotors() {
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, LOW);
}