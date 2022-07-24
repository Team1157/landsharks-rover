//#include <Arduino.h>
//#include <Bme280.h>
//#include <Adafruit_Sensor.h>
//#include <Adafruit_BNO055.h>
//
//Bme280TwoWire bmeInternal;
//Bme280TwoWire bmeExternal;
//
//Adafruit_BNO055 mainImu = Adafruit_BNO055(55); // imu is taken by the sensor library :(
//
//void setup() {
//  Serial.begin(9600);
//  Wire.begin((int) Bme280TwoWireAddress::Primary);
//  Wire.begin((int) Bme280TwoWireAddress::Secondary);
//
//  Serial.println();
//
//  bmeInternal.begin(Bme280TwoWireAddress::Primary);
//  bmeInternal.setSettings(Bme280Settings::indoor()); //TODO figure out most appropiate sensor settings
//
//  bmeExternal.begin(Bme280TwoWireAddress::Secondary);
//  bmeExternal.setSettings(Bme280Settings::indoor());
//}
//
//void loop() {
//  int startTime = millis();
//  float tempInternal = bmeInternal.getTemperature();
//  float tempExternal = bmeExternal.getTemperature();
//  float pressureInternal = bmeInternal.getPressure();
//  float pressureExternal = bmeExternal.getPressure();
//  float humidityInternal = bmeInternal.getHumidity();
//  float humidityExternal = bmeExternal.getHumidity();
//  int endTime = millis();
//
//  Serial.println("Internal: " + String(tempInternal) + " °C, " + String(pressureInternal) + " Pa, " + String(humidityInternal) + "%");
//  Serial.println("External: " + String(tempExternal) + " °C, " + String(pressureExternal) + " Pa, " + String(humidityExternal) + "%");
//  Serial.println(endTime - startTime);
// 
//  delay(10000);
//}
