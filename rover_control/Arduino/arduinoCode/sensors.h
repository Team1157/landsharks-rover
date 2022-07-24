#ifndef SENSORS_H
#define SENSORS_H

namespace sensor {

class Sensor {
  public:
    struct SensorData {
      unsigned long timestamp; // millis since startup
    } lastData;
    
    struct SensorSettings {
      int pollInterval; // in millis
      int messageInterval; // in millis
    } settings;

    Sensor(String sensorName, int pollInterval, int messageInterval);
    void periodic();
    void setEnabled(bool enable);

  protected:
    String sensorName;
    bool enabled;
    
  private:
    unsigned long lastPollTime;
    unsigned long lastMessageTime;
  
    void poll();
    void sendData();
};

class BME280: Sensor {
  public:
    struct BME280Data: SensorData {
      float temp; // Degrees Celcius
      float humidity; // %
      float pressure; // Pascals
    } lastData;

    BME280(String sensorName, int pollInterval = 5000, int messageInterval = 5000, bool altAddress = false);

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
  
    BNO055(String sensorName, int pollInterval = 5000, int messageInterval = 5000);

  private:
    Adafruit_BNO055 bno;

    void poll();
    void sendData();
};

}

#endif
