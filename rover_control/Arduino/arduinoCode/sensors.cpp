#include <Arduino.h>
#include <Bme280.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BNO055.h>
#include "sensors.h"

namespace sensor {

Sensor::Sensor(String sensorName, int pollInterval, int messageInterval) {
  this->sensorName = sensorName;
  settings = SensorSettings{pollInterval, messageInterval};
  setEnabled(true);
}

void Sensor::periodic() {
  if(!enabled) {
    return;
  }
  
  unsigned long now = millis();
  if(now - lastPollTime >= settings.pollInterval) {
    poll();
    lastPollTime %= settings.pollInterval;
  }
  if(now - lastMessageTime >= settings.messageInterval) {
    sendData();
    lastMessageTime %= settings.messageInterval;
  }
}

void Sensor::setEnabled(bool enabled) {
  this->enabled = enabled;
  if(enabled) {
    unsigned long now = millis();
    lastPollTime = now;
    lastMessageTime = now;
  }
}

BME280::BME280(String sensorName, int pollInterval, int messageInterval, bool altAddress):
Sensor(sensorName, pollInterval, messageInterval) {
  Bme280TwoWireAddress addr = altAddress ? Bme280TwoWireAddress::Secondary : Bme280TwoWireAddress::Primary;
  Wire.begin((char) addr);
  bme.begin(addr);
}

void BME280::poll() {
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

BNO055::BNO055(String sensorName, int pollInterval, int messageInterval):
Sensor(sensorName, pollInterval, messageInterval){
  bno = Adafruit_BNO055(55, 0x28);
  bno.begin();
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
