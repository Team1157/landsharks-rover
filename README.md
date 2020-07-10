# Landsharks Rover
This repository contains the control code for the rover and the base station.
## Control Protocol
The control protocol is a simple WebSockets message-based protocol. Messages are
encoded in JSON and all contain a `"type"` key, which is one of the following values:
### `"log"`: Shows info
Rover -> Base, Base -> Driver  
Response: None
```json
{
    "type": "log",
    "message": "Some message", // Human-readable message to display to the driver
    "level": "info" // Severity or "level" of the message (debug, info, warning, error)
}
```
### `"command"`: Runs a command
Driver -> Base, Base -> Rover  
Response: `"command_response"` or `"error"`
```json
{
    "type": "command",
    "id": 17574336, // A unique ID used to match commands with responses
    "command": "move", // The command to run
    "parameters": { // A dictionary of parameters, as defined by the command
        "distance": 1
    }
}
```
### `"command_response"`: Returns command status and data
Rover -> Base, Base -> Driver  
Response: None
```json
{
    "type": "command_response",
    "id": 17574336, // The ID of the command that's being responded to
    "error": null //A string representing an error or null
    "contents: {} // Any other info from the command
}
```
### `"status"`: Returns command status and data
Rover -> Base  
Response: None
```json
{
  "type": "status",
  "status": "busy", // Whether the rover is running a command ("busy" or "idle")
  "current_command": 12345678 // The current command id or null
}
```
### `"clear_queue"`: Cancels all commands in the queue
Driver -> Base  
Response: `"queue_status"`
```json
{
    "type": "clear_queue"
}
```
### `"queue_status"`: Returns all commands in the queue
Base -> Driver  
Response: None
```json
{
    "type": "queue_status",
    "current_command": { // The full message that initiated the running command
        "type": "command",
        "id": 14550083,
        "command": "move_camera",
        "parameters": {
            "pan": 48.566,
            "tilt": -21.093
        }
    },
    "queued_commands": [ // The list of the commands in the queue
        {
            "type": "command",
            "id": 17574336,
            "command": "move",
            "parameters": {
                "distance": 1
            }
        },
        ...
    ]
}
```
### `"option"`: Sets or gets options
Driver -> Base, Base -> Rover  
Response: `"option_response"`
```json
{
    "type": "option",
    "get": [ // Any options to get
        "camera_framerate"
    ],
    "set": { // Any options to set
        "digest_interval": 1
    }
}
```
### `"option_response"`: Returns option values
Rover -> Base, Base -> Driver  
Response: None
```json
{
    "type": "option_response",
    "values": { // The values of all options set and get
        "camera_framerate": 5,
        "digest_interval": 1 // May be different from set value if invalid
    }
}
```
### `"digest"`: Reports sensor values
Rover -> Base, Base -> Driver  
Response: None
```json
{
    "type": "digest",
    "sensors": { // The values of each sensor reported
        "imu": {...},
        "humidity": ... 
    }
}
```
### `"error"`: Reports error in protocol
Driver <-> Base, Base <-> Rover
Response: None
```json
{
    "type": "error",
    "error": "json_parse_error", // The error type
    "message": "" // A human readable message to be displayed to the drivers
}
```
### `"e_stop"`: Stops all commands and clears queue
Driver -> Base, Base -> Rover
Response: `status`
```json
{
    "type": "e_stop",
}
```
###Periodic messages 
These messages are sent automatically with a frequency usually configurable with the options message
* `"status"` (Rover -> Base)
* `"digest"` (Rover -> Baser)
* `"queue_status"` (Base -> Driver)
  
Todo: `"auth"`