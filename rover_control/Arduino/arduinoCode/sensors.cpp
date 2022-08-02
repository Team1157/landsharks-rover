#include <Arduino.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>
#include <Adafruit_BNO055.h>
#include <Adafruit_INA260.h>

#include "sensors.h"

// Print to serial with a trailing space
#define SP(...) { Serial.print(__VA_ARGS__); Serial.print(' '); }

Sensor::Sensor(char* sensorName) {
  this->sensorName = sensorName;
}

void Sensor::callback() {
  poll();
  sendData();
  Serial.print('\n');
}

void Sensor::init() {}

void Sensor::sendData() {
  SP("data");
  SP(sensorName);
}

BME280::BME280(char* sensorName, bool altAddress):
Sensor(sensorName) {
  this->altAddress = altAddress;
}

void BME280::init() {
  bme.begin(altAddress ? 0x77 : 0x76);
}

void BME280::poll() {
  lastData.temp = bme.readTemperature();
  lastData.humidity = bme.readHumidity();
  lastData.pressure = bme.readPressure();
}

void BME280::sendData() {
  Sensor::sendData();
  SP(lastData.temp, 2);
  SP(lastData.humidity, 2);
  SP(lastData.pressure, 0);
}

BNO055::BNO055(char* sensorName):
Sensor(sensorName), bno(55, 0x28) {}

void BNO055::init() {
  bno.begin();
}

void BNO055::poll() {
  bno.getEvent(&event, Adafruit_BNO055::VECTOR_EULER);
  lastData.roll = event.orientation.z > 0 ? event.orientation.z - 180 : event.orientation.z + 180;
  lastData.pitch = -event.orientation.y;
  lastData.yaw = event.orientation.x;
  
  lastData.temp = bno.getTemp();
}

void BNO055::sendData() {
  Sensor::sendData();
  SP(lastData.roll, 2);
  SP(lastData.pitch, 2);
  SP(lastData.yaw, 2);
  SP(lastData.temp);
}

AnalogCurrent::AnalogCurrent(char* sensorName):
Sensor(sensorName) {}

void AnalogCurrent::poll() {
  current = map(analogRead(A0), 511, 94, 0, 509); 
}

void AnalogCurrent::sendData() {
  Sensor::sendData();
  SP(current);
}

INA260::INA260(char* sensorName):
Sensor(sensorName) {}

void INA260::init() {
  ina.begin();
}

void INA260::poll() {
  voltage = ina.readBusVoltage() / 1000;
  current = ina.readCurrent() / 1000;
}

void INA260::sendData() {
  Sensor::sendData();
  SP(voltage, 2);
  SP(current, 2);
}
