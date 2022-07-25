#include "parser.h"
#define CHECK_ARGS(scan, num) \
  if (scan != num) { \
    Serial.println("log error Failed to parse args") \
    break;\
  }

char command_buf[256] = {'\0'};
size_t command_buf_index = 0; // bounded 0 to 254
bool command_buf_overrun = false;

void read_serial_task() {
  int r;
  while ((r = Serial.read()) != -1) {
    if (r == '\n') {
      command_buf[command_buf_index] = '\0';
      command_buf_index = 0;
      if (command_buf_overrun) {
        command_buf_overrun = false;
      }
      else {
        execute_command()
      }
    }
    else {
      command_buf[command_buf_index] = r;
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
  switch command_buf[0] {
    case 'e': { // Echo
      // Return rest of buffer raw
      Serial.print("echo ");
      Serial.println(command_buffer+1);
      break;
    }
    case 'p': { // Camera pan
      uint16_t yaw, pitch;
      CHECK_ARGS(sscanf(command_buffer+1, "%d %d", yaw, pitch), 2);
      // TODO
      break;
    }
    case 'd': { // Move distance
      uint16_t dist, spd, angle;
      CHECK_ARGS(sscanf(command_buffer+1, "%d %d %d", dist, spd, angle), 3);
      // TODO
      break;
    }
    case 'c': { // Move continuous
      uint16_t spd, angle;
      CHECK_ARGS(sscanf(command_buffer+1,"%d %d", spd, angle), 3);
      // TODO
      break;
    }
    default: {
      Serial.print("log error Unknown command specifier ");
      Serial.println(command_buffer[0]);
    }
  }
}
