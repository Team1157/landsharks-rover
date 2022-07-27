#include <YetAnotherPcInt.h>
#include <TaskScheduler.h>
#include <Servo.h>

#include "parser.h"

#define PAN_PWM_PIN 2
#define PAN_ENCODER_PIN 3
#define TILT_PWM_PIN 12
#define PANEL_CURRENT_PIN A0

const byte ENC_INT_PINS[] = {62, 63, 64, 65, 66, 67}, //main triggers for the encoder interrupts
           ENC_DIR_PINS[] = {22, 23, 24, 25, 26, 27}, //secondary encoder pins for finding direction
           MOT_PWM_PINS[] = { 4,  7,  8,  9, 10, 11}, //pwm outputs for motors
           MOT_DIR_PINS[] = {53, 52, 51, 50, 49, 48}, //directional select for motors
           PIR_PINS[] = {10, 11, 12, 13};

const bool INVERT_MOTORS[] = { 0,  1,  0,  1,  0,  1}; // A 1 indicates a motor is inverted

const int MOT_P_GAIN = 0;
const int MOT_I_GAIN = 0;

byte INDICES[] = {0, 1, 2, 3, 4, 5};

int8_t encCountStep[6] = {0}; // The number to increment by each time an encoder ticks forward, determined by INVERT_MOTORS

volatile long encCount[6] = {0}; // The cumulative total count of encoder ticks for each encoder
long lastEncCount[6] = {0};
unsigned long lastMotUpdates[6] = {0};
int lastErr[6] = {0};
int motSetpoints[6] = {0}; // Between -1000000000 and 1000000000

Servo panServo;
Servo tiltServo;

byte targetTiltAngle = 90;
byte targetPanAngle = 0;
volatile unsigned long panEncLastPulseStart = 0;
volatile unsigned int panEncLastPulseLength = 0;
int panAngle;

Scheduler scheduler;

void driveTaskCallback();
void stopMotors();
void moveCameraTaskCallback();
Task readSerialTask(10, TASK_FOREVER, &read_serial_task, &scheduler); 
Task driveTask(20, TASK_FOREVER, &driveTaskCallback, &scheduler, false, nullptr, stopMotors);
Task moveCameraTask(20, TASK_FOREVER, &moveCameraTaskCallback, &scheduler);

void setup() {
  // Drive motor setup
  for(byte i = 0; i < 6; i++) {
    pinMode(ENC_INT_PINS[i], INPUT);
    pinMode(ENC_DIR_PINS[i], INPUT);

    pinMode(MOT_PWM_PINS[i], OUTPUT);
    pinMode(MOT_DIR_PINS[i], OUTPUT);

    if(INVERT_MOTORS[i]) { //set the count step for each motor
      encCountStep[i] = -1;
    }
    else {
      encCountStep[i] = 1;
    }

    PcInt::attachInterrupt(ENC_INT_PINS[i], handleInterrupt, &INDICES[i], CHANGE);
  }

  // Pretticam pan tilt setup
  panServo.attach(PAN_PWM_PIN);
  tiltServo.attach(TILT_PWM_PIN);

  pinMode(PAN_ENCODER_PIN, INPUT);
  attachInterrupt(digitalPinToInterrupt(PAN_ENCODER_PIN), panEncCallback, CHANGE);

  Serial.begin(115200);

  readSerialTask.enable();
  moveCameraTask.enable();
}

void handleInterrupt(byte *index, bool pinState) {
  encCount[*index] += encCountStep[*index] * (digitalRead((ENC_DIR_PINS[*index]) ^ pinState) * 2 - 1);
}

long newCount;
long deltaCount;
unsigned long currMicros;
unsigned long deltaMicros;
int err;
int deltaErr;

void updateMotorController(byte index, int setpoint) { // Target velocity in clicks per second
  // Get clicks since last loop
  noInterrupts();
  newCount = encCount[index];
  interrupts();
  deltaCount = newCount - lastEncCount[index];
  lastEncCount[index] = newCount;

  // Get time since last loop
  currMicros = micros();
  deltaMicros = currMicros - lastMotUpdates[index];
  lastMotUpdates[index] = currMicros;

  // Calculate the difference between the current and target velocity in clicks per second
  err = setpoint - deltaCount * 1000000 / deltaMicros;
  deltaErr = err - lastErr[index];
  lastErr[index] = err;

  // Calculate the velocity PID algorithm from err and gains
  motSetpoints[index] += MOT_P_GAIN * deltaErr + MOT_I_GAIN * err * deltaMicros / 1000;
  motSetpoints[index] = constrain(motSetpoints[index], -1000000000, 1000000000);

  // Write setpoint to motor
  digitalWrite(MOT_DIR_PINS[index], motSetpoints[index] < 0);
  analogWrite(MOT_PWM_PINS[index], abs(motSetpoints[index]) * 255 / 1000000000);
}

void resetController(byte index) {
  motSetpoints[index] = 0;
  lastEncCount[index] = 0;
  
  lastMotUpdates[index] = micros();
  
  noInterrupts();
  encCount[index] = 0;
  interrupts();
}

void driveTaskCallback() {
  if(driveTask.isFirstIteration()) {
    for(byte i = 0; i < 6; i++) {
      resetController(i);
    }
  } else {
    
  }
}


void stopMotors() {
  for(byte i; i < 6; i++) {
    digitalWrite(MOT_PWM_PINS[i], LOW);
  }
}

void moveDistanceCommand(uint16_t dist, uint16_t spd, uint16_t angle) {
  
}

void panEncCallback() {
  if (digitalRead(PAN_ENCODER_PIN)) {
    panEncLastPulseStart = micros();
  } else {
    panEncLastPulseLength = micros() - panEncLastPulseStart;
  }
}

unsigned int pulseLength;
void moveCameraTaskCallback() {
  int setpoint = map(targetTiltAngle, 0, 110, 1825, 875);
  setpoint = constrain(setpoint, 875, 1825);
  tiltServo.writeMicroseconds(setpoint);

  noInterrupts();
  pulseLength = panEncLastPulseLength;
  interrupts();
  int newAngle = map(pulseLength, 29, 1045, 0, 359);

  if (abs(((newAngle - panAngle + 540) % 360) - 180) < 25) {
    panAngle = newAngle;
  }

  int err = ((targetPanAngle - panAngle + 540) % 360) - 180;
  setpoint = 1500 - err * 3 ;
  setpoint = constrain(setpoint, 1350, 1650);
  panServo.writeMicroseconds(setpoint);
}

void moveCameraCommand(uint16_t yaw, uint16_t pitch) {
  targetPanAngle = yaw;
  targetTiltAngle = pitch;
}


void loop() {
  scheduler.execute();
}
