#pragma once
#include <stdint.h>

void read_serial_task();

void moveCameraCommand(uint16_t yaw, uint16_t pitch); // degrees, degrees

void moveDistanceCommand(int16_t dist, uint16_t spd, uint16_t angle); // mm, mm/s, degrees

void eStopCommand();
