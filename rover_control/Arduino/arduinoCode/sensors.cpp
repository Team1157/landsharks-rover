#include <Arduino.h>
#include <Bme280.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BNO055.h>

#include "sensors.h"

namespace sensor {

Sensor::Sensor(Scheduler scheduler, String sensorName, int pollInterval) {
  this->sensorName = sensorName;
//  this->pollTask = Task(pollInterval, TASK_FOREVER, &this->callback, &scheduler);
  
  setEnabled(true);
}

void Sensor::setEnabled(bool enabled) {
  if (enabled) {
    this->pollTask.enableIfNot();
  } else {
    this->pollTask.disable();
  }
}

void Sensor::callback() {
  poll();
  sendData();
}

BME280::BME280(Scheduler scheduler, String sensorName, int pollInterval = 5000, bool altAddress = false):
Sensor(scheduler, sensorName, pollInterval) {
  Bme280TwoWireAddress addr = altAddress ? Bme280TwoWireAddress::Secondary : Bme280TwoWireAddress::Primary;
  Wire.begin((char) addr);
  bme.begin(addr);
}

void BME280::poll() {
  lastData.timestamp = millis();
  lastData.temp = bme.getTemperature();
  lastData.humidity = bme.getHumidity();
  lastData.pressure = bme.getPressure();
}

void BME280::sendData() {
  Serial1.println(sensorName + 
    F(" timestamp ") + String(lastData.timestamp) + 
    F(" temp ") + String(lastData.temp, 2) + 
    F(" humidity ") + String(lastData.humidity, 2) + 
    F(" pressure ") + String((int) lastData.pressure)
  );
}

BNO055::BNO055(Scheduler scheduler, String sensorName, int pollInterval = 5000):
Sensor(scheduler, sensorName, pollInterval){
  bno = Adafruit_BNO055(55, 0x28);
  bno.begin();
}

void BNO055::poll() {
  lastData.timestamp = millis();
  // TODO
}

void BNO055::sendData() {
  Serial1.println(sensorName + 
    F(" timestamp ") + String(lastData.timestamp) + 
    F(" x_accel ") + String(lastData.x_accel, 2) + 
    F(" y_accel ") + String(lastData.y_accel, 2) + 
    F(" z_accel ") + String(lastData.z_accel, 2) + 
    F(" roll ") + String(lastData.roll, 2) + 
    F(" pitch ") + String(lastData.pitch, 2) + 
    F(" yaw ") + String(lastData.yaw, 2)
  );
}

}
