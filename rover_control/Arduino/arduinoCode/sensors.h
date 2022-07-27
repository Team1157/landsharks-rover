#pragma once

#include <TaskSchedulerDeclarations.h>

namespace sensor {

class Sensor {
  public:
    struct SensorData {
      unsigned long timestamp; // millis since startup
    } lastData;

    Task pollTask;

    Sensor(Scheduler scheduler, String sensorName, int pollInterval);
    void periodic();
    void setEnabled(bool enable);

  protected:
    String sensorName;
    
  private:
    void poll();
    void sendData();
    void callback();
};

class BME280: Sensor {
  public:
    struct BME280Data: SensorData {
      float temp; // Degrees Celcius
      float humidity; // %
      float pressure; // Pascals
    } lastData;

    BME280(Scheduler scheduler, String sensorName, int messageInterval = 5000, bool altAddress = false);

  private:
    Bme280TwoWire bme;

    void poll();
    void sendData();
};

class BNO055: Sensor {
  public:
    struct BNO055Data: SensorData {
      double x_accel;
      double y_accel;
      double z_accel;
      double roll;
      double pitch;
      double yaw;
    } lastData;
  
    BNO055(Scheduler scheduler, String sensorName, int pollInterval = 5000);

  private:
    Adafruit_BNO055 bno;

    void poll();
    void sendData();
};

}
