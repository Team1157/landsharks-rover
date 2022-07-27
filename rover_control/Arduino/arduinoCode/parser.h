#pragma once
#include <stdint.h>

void read_serial_task();

void moveCameraCommand(uint16_t yaw, uint16_t pitch);

void moveDistanceCommand(uint16_t dist, uint16_t spd, uint16_t angle);
