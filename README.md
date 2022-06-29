# Sandshark
This repository contains all the code for the Landsharks rover project. This readme defines several
protocols, file formats, and utility programs used in the project.

## Control Protocol (Driver Station ↔ Base Station ↔ Rover)
The control protocol is a simple WebSockets message-based protocol. Messages are
encoded in JSON and all contain a `"type"` key, which defines the message type.

### Command types

#### `"log"`: Shows info
Driver ↔ Base ← Rover  
Response: none
```js
{
    "type": "log",
    "message": "Some message", // Human-readable message to display to the driver
    "level": "info" // Severity or "level" of the message (debug, info, warning, error)
}
```

#### `"command"`: Runs a command
Driver → Base → Rover  
Response: `Driver → Base: None, Base → Rover: "status", "command_response" (when finished)`
```js
{
    "type": "command",
    "id": 17574336, // A unique ID used to match commands with responses (always null Driver → Base)
    "command": "move", // The command to run. null cancels the running command
    "parameters": { // A dictionary of parameters, as defined by the command
        "distance": 1
    }
}
```

#### `"command_response"`: Returns command status and data
Driver ← Base ← Rover  
Response: none
```js
{
    "type": "command_response",
    "id": 17574336, // The ID of the command that's being responded to
    "error": null // Error type or null if none
    "contents": {} // Any other returned info from the command
}
```

#### `"status"`: Returns command status and data
Base ← Rover  
Response: none
```js
{
  "type": "status",
  "status": "busy", // Whether the rover is running a command ("busy" or "idle")
  "current_command": 12345678 // The current command id or null if idle
}
```

#### `"option"`: Sets or gets options
Driver → Base → Rover  
Response: `"option_response"`
```js
{
    // Both set and get are required, can be empty
    "type": "option",
    "get": [ // Any options to get
        "navcam.framerate"
    ],
    "set": { // Any options to set
        "imu.message_interval": 1
    }
}
```

#### `"option_response"`: Returns option values
Driver ← Base ← Rover  
Response: none
```js
{
    "type": "option_response",
    "values": { // The values of all options set and get
        "navcam.framerate": 5,
        "imu.message_interval": 1 // May be different from set value if invalid
    }
}
```

#### `"measurement"`: Reports sensor values
Driver ← Base ← Rover  
Response: none
```js
{
    "type": "sensor",
    "time": 1600896055730369100, // Unix timestamp, in nanoseconds
    "measurements": { // The values of each sensor reported
        "x_accel": 3.2, // A specific value of the sensor (passed to Influx as a field)
        ...
    }
}
```

#### `"query"`: Gets a value from the base station
Driver → Base  
Response: `"query_response"`
```js
{
    "type": "query",
    "query": "client_list"
}
```

#### `"query_response"`: Returns a value from the base station to the driver
Driver ← Base  
Response: none
```js
{
    "type": "query_response",
    "query": "client_list",
    "value": // Any object
}
```

#### `"e_stop"`: Stops all commands
Driver → Base → Rover  
Response: `Driver → Base: "queue_status", Base → Rover: "status"`
```js
{
    "type": "e_stop"
}
```

#### `"auth"`: Handles authentication
Driver → Base ← Rover  
Response: `"auth_response"`, disconnect if unsuccessful
```js
{
    "type": "auth",
    "token": 123456,
}
```

#### `"auth_response"`: Handles authentication
Driver ← Base → Rover  
```js
{
    "type": "auth_response",
    "success": true
}
```

### Periodic messages 
These messages are sent automatically with a frequency configurable with the options message.
- `"status"` (Base ← Rover)
- `"sensors"` (Base ← Rover)

## On-rover protocol (Raspberry Pi ↔ Arduino)
Serial-based protocol for communicating between RPi and Arduino.  
TODO: define protocol

## User authentication "database": `users.json`
This file contains hashed passwords and permission groups of all registered rover users.
It is encoded in JSON format.
```js
{
    1234567: { // User token
        "username": "",
        "groups": ["drivers"] // groups are "viewers", "drivers", "rovers"
    }
}
```
Rather than editing directly, user details should be modified with the `rover_user.py` utility
script.
```shell script
python rover_user.py add <user>  # adds a user
python rover_user.py remove <user>  # removes a user
python rover_user.py list-users  # lists all registered users
python rover_user.py change-token <user>  # changes a user's token
python rover_user.py add-groups <user> <groups>  # adds a user to one or more groups
python rover_user.py remove-groups <user> <groups>  # removes a user from one or more groups
python rover_user.py list-groups <user>  # lists the groups the user belongs to
```