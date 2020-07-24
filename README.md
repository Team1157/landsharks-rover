# Landsharks Rover
This repository contains the control code for the rover and the base station.
## Control Protocol
The control protocol is a simple WebSockets message-based protocol. Messages are
encoded in JSON and all contain a `"type"` key, which is one of the following values:
### `"log"`: Shows info
Driver ↔ Base ← Rover  
Response: none
```js
{
    "type": "log",
    "message": "Some message", // Human-readable message to display to the driver
    "level": "info" // Severity or "level" of the message (debug, info, warning, error)
}
```
### `"command"`: Runs a command
Driver → Base → Rover  
Response: `"command_response"`
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
Driver ← Base ← Rover  
Response: none
```js
{
    "type": "command_response",
    "id": 17574336, // The ID of the command that's being responded to
    "error": null // Error type or null if none
    "contents: {} // Any other returned info from the command
}
```
### `"status"`: Returns command status and data
Base ← Rover  
Response: none
```js
{
  "type": "status",
  "status": "busy", // Whether the rover is running a command ("busy" or "idle")
  "current_command": 12345678 // The current command id or null if idle
}
```
### `"clear_queue"`: Cancels all commands in the queue
Driver → Base  
Response: `"queue_status"`
```js
{
    "type": "clear_queue"
}
```
### `"queue_status"`: Returns all commands in the queue
Driver ← Base  
Response: none
```js
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
Driver → Base → Rover  
Response: `"option_response"`
```js
{
    // Both set and get are required, can be empty
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
Driver ← Base ← Rover  
Response: none
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
Driver ← Base ← Rover  
Response: none
```js
// Every sensor must be reported everytime, but can report null
{
    "type": "digest",
    "sensors": { // The values of each sensor reported
        "imu": {
            "x_accel": 3.2,
            ... 
        },
        "humidity": ... 
    }
}
```
### `"query"`: Gets a value from the base station
Driver → Base  
Response: `"query_response"`
```js
{
    "type": "query",
    "query": "client_list"
}
```
### `"query_response"`: Returns a value from the base station to the driver
Driver ← Base  
Response: none
```js
{
    "type": "query_response",
    "query": "client_list",
    "value": // Any object
}
```
### `"error"`: Reports error in protocol
Driver ↔ Base ↔ Rover  
Response: none
```js
{
    "type": "error",
    "error": "json_parse_error", // The error type
    "message": "Received message with malformed JSON" // Human readable message to be displayed to the drivers
}
```
### `"e_stop"`: Stops all commands and clears queue
Driver → Base → Rover  
Response: `status`
```js
{
    "type": "e_stop"
}
```
### `"auth"`: Handles authentication
Driver → Base ← Rover  
Response: none if successful, disconnect if unsuccessful
```js
{
    "type": "auth",
    "user": "username",
    "pass": "password" // Plaintext is OK over secure (WSS) connection
}
```
###Periodic messages 
These messages are sent automatically with a frequency usually configurable with the options message
* `"status"` (Base ← Rover)
* `"digest"` (Base ← Rover)
* `"queue_status"` (Driver ← Base)