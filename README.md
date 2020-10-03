# Landsharks Rover
This repository contains all of the code for the rover project. This readme defines several
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
Response: `Driver → Base: "queue_status", Base → Rover: "command_response" (after delay)`
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

#### `"command_response"`: Returns command status and data
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

#### `"clear_queue"`: Cancels all commands in the queue
Driver → Base  
Response: `"queue_status"`
```js
{
    "type": "clear_queue"
}
```

#### `"queue_status"`: Returns all commands in the queue
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

#### `"option"`: Sets or gets options
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
        "sensors_interval": 1
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
        "camera_framerate": 5,
        "sensors_interval": 1 // May be different from set value if invalid
    }
}
```

#### `"sensors"`: Reports sensor values
Driver ← Base ← Rover  
Response: none
```js
{
    "type": "sensors",
    "time": 1600896055730369100, // Unix timestamp, in nanoseconds
    "sensors": { // The values of each sensor reported
        "imu": { // The measurement of a specific sensor (passed to Influx as a measurement)
            "x_accel": 3.2, // A specific value of the sensor (passed to Influx as a field)
            ... 
        },
        "humidity": ... 
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

#### `"error"`: Reports error in protocol
Driver ↔ Base ↔ Rover  
Response: none
```js
{
    "type": "error",
    "error": "json_parse_error", // The error type
    "message": "Received message with malformed JSON" // Human readable message to be displayed to the drivers
}
```

#### `"e_stop"`: Stops all commands and clears queue
Driver → Base → Rover  
Response: `status`
```js
{
    "type": "e_stop"
}
```

#### `"auth"`: Handles authentication
Driver → Base ← Rover  
Response: none if successful, disconnect if unsuccessful
```js
{
    "type": "auth",
    "user": "username",
    "pass": "password" // Plaintext is OK over secure (WSS) connection
}
```

### Periodic messages 
These messages are sent automatically with a frequency configurable with the options message.
- `"status"` (Base ← Rover)
- `"sensors"` (Base ← Rover)
- `"queue_status"` (Driver ← Base)

## On-rover protocol (Raspberry Pi ↔ Arduino)
Serial-based protocol for communicating between RPi and Arduino.  
TODO: define protocol

## User authentication "database": `rover_users.json`
This file contains hashed passwords and permission groups of all registered rover users.
It is encoded in JSON format.
```js
{
    "<username>": { // Each user is a key on the root object of the JSON file
        "pw_hash": "<bcrypt_hash>", // User's bcrypt hashed and salted password
        "groups": [] // Any permission groups the user is in, such as "rover" or "driver"
    }
}
```
Rather than editing directly, user details should be modified with the `rover_user.py` utility
script.
```shell script
python rover_user.py add <user>  # adds a user
python rover_user.py remove <user>  # removes a user
python rover_user.py list-users  # lists all registered users
python rover_user.py change-password <user>  # changes a user's password
python rover_user.py add-groups <user> <groups>  # adds a user to one or more groups
python rover_user.py remove-groups <user> <groups>  # removes a user from one or more groups
python rover_user.py list-groups <user>  # lists the groups the user belongs to
```