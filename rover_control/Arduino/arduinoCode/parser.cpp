#include "parser.h"

#include <Arduino.h>
#include <stdint.h>

#define CHECK_ARGS(scan, num) \
  if (scan != num) { \
    Serial.println("log error Failed to parse args"); \
    break;\
  }

char command_buffer[256] = {'\0'};
size_t command_buf_index = 0; // bounded 0 to 254
bool command_buf_overrun = false;

uint32_t lastMessageMillis = 0;

uint32_t getLastMessageMillis() {
  return lastMessageMillis();
}

void execute_command();

void read_serial_task() {
  int r;
  while ((r = Serial.read()) != -1) {
    if (r == '\n') {
      lastMessageMillis = millis();
      
      command_buffer[command_buf_index] = '\0';
      if (command_buf_overrun) {
        command_buf_overrun = false;
      }
      else if (command_buf_index != 0) { // Don't execute for empty buffer
        execute_command();
      }
      command_buf_index = 0;
    }
    else {
      command_buffer[command_buf_index] = r;
      command_buf_index++;
    }
    if (command_buf_index >= 255) {
      Serial.println("log error Command buffer overrun");
      command_buf_index = 0;
      command_buf_overrun = true;
    }
  }
}

void execute_command() {
  // Read the command specifier
  switch (command_buffer[0]) {
    case 'h': { // Heartbeat
      Serial.println("hb");
    }
    case 'e': { // Echo
      // Return rest of buffer raw
      Serial.print("echo ");
      Serial.println(command_buffer+1);
      break;
    }
    case 'p': { // Camera pan
      uint16_t yaw, pitch;
      CHECK_ARGS(sscanf(command_buffer+1, "%u %u", &yaw, &pitch), 2);
      moveCameraCommand(yaw, pitch);
      break;
    }
    case 'd': { // Move distance
      int16_t dist, angle;
      uint16_t spd;
      CHECK_ARGS(sscanf(command_buffer+1, "%d %u %d", &dist, &spd, &angle), 3);
      moveDistanceCommand(dist, spd, angle);
      break;
    }
    case 'c': { // Move continuous
      uint16_t spd, angle;
      CHECK_ARGS(sscanf(command_buffer+1, "%u %u", &spd, &angle), 2);
      // TODO
      break;
    }
    case 'x': // Cancel command
    case '!': // E-stop
    {
      eStopCommand(); // Both cancel command and e-stop have the same functionality here
      break;
    }
    default: {
      Serial.print("log error Unknown command specifier ");
      Serial.println(command_buffer[0]);
    }
  }
}
