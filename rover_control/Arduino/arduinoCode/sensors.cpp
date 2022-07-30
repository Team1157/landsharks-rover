#include <Arduino.h>
#include <Bme280.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BNO055.h>
#include <Adafruit_INA260.h>

#include "sensors.h"

Sensor::Sensor(String sensorName) {
  this->sensorName = sensorName;
}

void Sensor::callback() {
  poll();
  sendData();
}

BME280::BME280(String sensorName, bool altAddress):
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
  Serial.println("data " + sensorName +
    String(lastData.temp, 2) +
    String(lastData.humidity, 2) +
    String((int) lastData.pressure)
  );
}

BNO055::BNO055(String sensorName):
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
  Serial.println("data " + sensorName +
    String(lastData.x_accel, 2) +
    String(lastData.y_accel, 2) +
    String(lastData.z_accel, 2) +
    String(lastData.roll, 2) +
    String(lastData.pitch, 2) +
    String(lastData.yaw, 2) +
    String(lastData.temp)
  );
}

AnalogCurrent::AnalogCurrent(String sensorName):
Sensor(sensorName) {}

void AnalogCurrent::poll() {
  current = map(analogRead(A0), 511, 94, 0, 509); 
}

void AnalogCurrent::sendData() {
  Serial.println("data " + sensorName +
    String(current)
  );
}

INA260::INA260(String sensorName):
Sensor(sensorName) {
  ina.begin();
}

void INA260::poll() {
  voltage = ina.readBusVoltage();
  current = ina.readCurrent();
}

void INA260::sendData() {
  Serial.println("data " + sensorName +
    String(voltage, 2) +
    String(current, 2)
  );
}
