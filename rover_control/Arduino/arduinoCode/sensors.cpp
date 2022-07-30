#include <Arduino.h>
#include <Bme280.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BNO055.h>
#include <Adafruit_INA260.h>

#include "sensors.h"

// Shared format buffer. Since each usage of this buffer will print it immediately after formatting, it's ok to share.
// I've made it static to avoid having large strings on the stack.
char fmt_buf[256];

Sensor::Sensor(char* sensorName) {
  this->sensorName = sensorName;
}

void Sensor::callback() {
  poll();
  sendData();
}

BME280::BME280(char* sensorName, bool altAddress):
Sensor(sensorName) {
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
  snprintf(
    fmt_buf, 256,
    "data %s %.2f %.2f %.0f",
    sensorName,
    lastData.temp,
    lastData.humidity,
    lastData.pressure
  );
  Serial.println(fmt_buf);
}

BNO055::BNO055(char* sensorName):
Sensor(sensorName){
  bno = Adafruit_BNO055(55, 0x28);
  bno.begin();
}

void BNO055::poll() {
  bno.getEvent(&event, Adafruit_BNO055::VECTOR_EULER);
  Serial.print("x: ");
  Serial.println(event.orientation.x);
  Serial.print("y: ");
  Serial.println(event.orientation.y);
  Serial.print("z: ");
  Serial.println(event.orientation.z);
  bno.getEvent(&event, Adafruit_BNO055::VECTOR_LINEARACCEL);
  lastData.temp = bno.getTemp();
}

void BNO055::sendData() {
  snprintf(
    fmt_buf, 256,
    "data %s %.2f %.2f %.2f %.2f %.2f %.2f %d",
    sensorName,
    lastData.x_accel,
    lastData.y_accel,
    lastData.z_accel,
    lastData.roll,
    lastData.pitch,
    lastData.yaw,
    lastData.temp
  );
  Serial.println(fmt_buf);
}

AnalogCurrent::AnalogCurrent(char* sensorName):
Sensor(sensorName) {}

void AnalogCurrent::poll() {
  current = map(analogRead(A0), 511, 94, 0, 509); 
}

void AnalogCurrent::sendData() {
  snprintf(
    fmt_buf, 256,
    "data %s %d",
    sensorName,
    current
  );
  Serial.println(fmt_buf);
}

INA260::INA260(char* sensorName):
Sensor(sensorName) {
  ina.begin();
}

void INA260::poll() {
  voltage = ina.readBusVoltage();
  current = ina.readCurrent();
}

void INA260::sendData() {
  snprintf(
    fmt_buf, 256,
    "data %s %.2f %.2f",
    sensorName,
    voltage,
    current
  );
  Serial.println(fmt_buf);
}
