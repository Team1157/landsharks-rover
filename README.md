# Landsharks Rover
This repository contains the control code for the rover and the base station.
## Control Protocol
The control protocol is a simple WebSockets message-based protocol. Messages are
encoded in JSON and all contain a `"type"` key, which is one of the following values:
### `"log"`: Shows info
```js
{
    "type": "log",
    "message": "Some message", // Human-readable message to display to the driver
    "level": "info" // Severity or "level" of the message (debug, info, warning, error)
}
```
### `"command"`: Runs a command
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
```js
{
    "type": "command_response",
    "id": 17574336, // The ID of the command that's being responded to
    "status": "ok", // Whether or not the command was successful
    "contents: {} // Any other info from the command
}
```
### `"option"`: Sets or gets options
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
```js
{
    "type": "digest",
    "sensors": { // The values of each sensor reported
        "imu": {...},
        "humidity": ... 
    }
}
```
Todo: `"auth"`, `"command_base"`, and `"error"` (if we're keeping it)