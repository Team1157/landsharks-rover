#pragma once

#include <Bme280.h>
#include <Adafruit_BNO055.h>
#include <Adafruit_INA260.h>

class Sensor {
  public:
    Sensor(char* sensorName);
    void callback();

  protected:
    char* sensorName;
    
  private:
    virtual void poll() = 0;
    virtual void sendData() = 0;
};

class BME280: public Sensor {
  public:
    struct BME280Data {
      float temp; // Degrees Celcius
      float humidity; // %
      float pressure; // Pascals
    } lastData;

    BME280(char* sensorName, bool altAddress = false);

  private:
    Bme280TwoWire bme;

    void poll();
    void sendData();
};

class BNO055: public Sensor {
  public:
    struct BNO055Data {
      float x_accel;
      float y_accel;
      float z_accel;
      float roll;
      float pitch;
      float yaw;
      int8_t temp;
    } lastData;
  
    BNO055(char* sensorName);

  private:
    Adafruit_BNO055 bno;
    sensors_event_t event;

    void poll();
    void sendData();
};

class AnalogCurrent: public Sensor {
  public:
    int current; // in deciamps
    AnalogCurrent(char* sensorName);

  private:
    void poll();
    void sendData();
};

class INA260: public Sensor {
  public:
    float voltage; // Volts
    float current; // Amps
    
    INA260(char* sensorName);

  private:
    Adafruit_INA260 ina;
  
    void poll();
    void sendData();
};
