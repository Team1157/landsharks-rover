# Landsharks Rover
This repository contains the control code for the rover and the base station.
## Control Protocol
The control protocol is a simple WebSockets message-based protocol. Messages are
encoded in JSON and all contain a `"type"` key, which is one of the following values:
### `"log"`: Shows info
Rover -> Base, Base -> Driver  
Response: None
```js
{
    "type": "log",
    "message": "Some message", // Human-readable message to display to the driver
    "level": "info" // Severity or "level" of the message (debug, info, warning, error)
}
```
### `"command"`: Runs a command
Driver -> Base, Base -> Rover  
Response: `"command_response"` or `"error"`
```js
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
```js
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
```js
{
  "type": "status",
  "status": "busy", // Whether the rover is running a command
  "current_command": some id
}
```
### `"cancel_commands"`: Cancels all commands in the queue
Driver -> Base  
Response: `"clear_queue"`
```js
{
    "type": "clear_queue"
}
```
### `"queue_status"`: Returns all commands in the queue
Base -> Driver  
Response: None
```js
{
    "type": "queue_status",
    "commands": [ // The ids of the commands in the queue
        17574336,
        63347571
    ]
}
```
### `"option"`: Sets or gets options
Driver -> Base, Base -> Rover  
Response: `"option_response"`
```js
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
```js
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
```js
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
```js
{
    "type": "error",
}
```
### `"e_stop"`: Stops all commands and clears queue
Driver -> Base, Base -> Rover
Response: `status`
```js
{
    "type": "e_stop",
}
```
Todo: `"auth"`