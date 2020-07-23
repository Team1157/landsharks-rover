#include <PID_v1.h>
/* motor pin layout
 * left|front|right  
 *        ^
 * m0  p2 - m3 p19
 *        |
 *        |
 * m1  p3 - m4 p20
 *        |
 *        |
 * m2 p18 - m5 p21
*/
const byte EncIntPin[] = { 2,  3, 18, 19, 20, 21}, //main triggers for the encoder interrupts
           EncDirPin[] = {22, 24, 26, 28, 30, 32}, //secondary encoder pins for finding direction. Weird numbers to free up PWM pins
           MotPwmPin[] = { 5,  6,  7,  8,  9, 10}, //pwm outputs for motors
           MotDirPin[] = {23, 25, 27, 29, 31, 33}; //directional select for motors

const bool InvertCtl[] = { 1,  1,  1,  0,  0,  0}; //if all motors are wired the same, one side will need to be inverted to count properly
long CountStep[6] = {0}; //count step set by InvertCt[]. Should always be +-1

volatile long Count[6] = {0}; //cumulative total count of encoder ticks

volatile double CurrentSpeed[6], //speed of motors read from encoders
                OutputSpeed[6],  //speed PID controller will output
                TargetSpeed[6];  //speed PID controller is trying to reach

//PID setup. Speed motor is at currently, speed PID is outputting to motor, speed target for motor, coefficients, direction.
PID M0(&CurrentSpeed[0], &OutputSpeed[0], &TargetSpeed[0], 2, 5, 1, DIRECT);
PID M1(&CurrentSpeed[1], &OutputSpeed[1], &TargetSpeed[1], 2, 5, 1, DIRECT);
PID M2(&CurrentSpeed[2], &OutputSpeed[2], &TargetSpeed[2], 2, 5, 1, DIRECT);
PID M3(&CurrentSpeed[3], &OutputSpeed[3], &TargetSpeed[3], 2, 5, 1, DIRECT);
PID M4(&CurrentSpeed[4], &OutputSpeed[4], &TargetSpeed[4], 2, 5, 1, DIRECT);
PID M5(&CurrentSpeed[5], &OutputSpeed[5], &TargetSpeed[5], 2, 5, 1, DIRECT);

void setup() {
  for(int i = 0; i < 6; i++) {
    pinMode(EncIntPin[i], INPUT);
    pinMode(EncDirPin[i], INPUT);

    pinMode(MotPwmPin[i], OUTPUT);
    pinMode(MotDirPin[i], OUTPUT);
    
    if(InvertCtl[i]) { //set the count step for each motor
      CountStep[i] = -1;
    }
    else {
      CountStep[i] = 1;
    }
  }

  //set each interrupt to happen as the motor transitions from low to high
  attachInterrupt(digitalPinToInterrupt(EncIntPin[0]), CountM0, RISING);
  attachInterrupt(digitalPinToInterrupt(EncIntPin[1]), CountM1, RISING);
  attachInterrupt(digitalPinToInterrupt(EncIntPin[2]), CountM2, RISING);
  attachInterrupt(digitalPinToInterrupt(EncIntPin[3]), CountM3, RISING);
  attachInterrupt(digitalPinToInterrupt(EncIntPin[4]), CountM4, RISING);
  attachInterrupt(digitalPinToInterrupt(EncIntPin[5]), CountM5, RISING);

  Serial.begin(19200);
  while(!Serial){
    ;//wait for serial port to begin program
  }
}

void loop() {
  long startCount[6];
  unsigned long startTime[6];
  
  for(int i = 0; i < 6; i++) {
    startCount[i] = Count[i];
    startTime[i] = micros(); //done per-motor for accuracy
  }
  
  delay(1000); //placeholder for main code

  for(int i = 0; i < 6; i++) {
    double counts = (Count[i] - startCount[i]);
    double elapsedTime = (micros() - startTime[i]);
    CurrentSpeed[i] = (1000000.0*counts)/(2994.6*elapsedTime);
    Serial.println(CurrentSpeed[i], 5);
  }
}

void CountGeneric (byte motor) {
  if(digitalRead(EncDirPin[motor]) == LOW){
    Count[motor] += CountStep[motor]; //increment by the countStep. This allows inverting of each motor without a conditional each interrupt
  }
  else {
    Count[motor] -= CountStep[motor]; 
  }
}

void CountM0 () {CountGeneric(0);}
void CountM1 () {CountGeneric(1);}
void CountM2 () {CountGeneric(2);}
void CountM3 () {CountGeneric(3);}
void CountM4 () {CountGeneric(4);}
void CountM5 () {CountGeneric(5);}
