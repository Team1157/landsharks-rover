#pragma once

#include <Bme280.h>
#include <Adafruit_BNO055.h>

class Sensor {
  public:
    Sensor(String sensorName);
    void callback();

  protected:
    String sensorName;
    
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

    BME280(String sensorName, bool altAddress = false);

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
    } lastData;
  
    BNO055(String sensorName);

  private:
    Adafruit_BNO055 bno;

    void poll();
    void sendData();
};

class AnalogCurrent: public Sensor {
  public:
    int current; // in deciamps
    AnalogCurrent(String sensorName);

  private:
    void poll();
    void sendData();
};
