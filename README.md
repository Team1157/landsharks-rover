# Sandshark
This repository contains all the code for the Landsharks rover project. This readme defines several
protocols, file formats, and utility programs used in the project.

## Control Protocol (Driver Station ↔ Base Station ↔ Rover)
The control protocol is a simple WebSockets message-based protocol. Messages are
encoded in JSON and all contain a `"type"` key, which defines the message type.

### Command types

#### `"e_stop"`: Emergency stop
Driver → Base → Rover \
Response: `Base → Rover: "status"`
```js
{
    "type": "e_stop"
}
```

#### `"log"`: Shows info
Driver ↔ Base ← Rover \
Response: none
```js
{
    "type": "log",
    "message": "Some message", // Human-readable message to display to the driver
    "level": "info" // Severity or "level" of the message (debug, info, warning, error)
}
```

#### `"command"`: Runs a command
Driver → Base → Rover \
Response: `Driver → Base: None, Base → Rover: "status", "command_response" (when finished)`
```js
{
    "type": "command",
    // The command object to run. null cancels the running command
    "command": {
        "type": "move", // The command type
        // A set of parameters, as defined by the command
        "distance": 1
    }
}
```

#### `"command_ended"`: Notifies when the current command ends
Driver ← Base ← Rover \
Response: none
```js
{
    "type": "command_ended",
    "completed": true // true if the command ran to completion, false otherwise
}
```

#### `"status"`: Returns the current command
Driver ← Base ← Rover \
Response: none
```js
{
    "type": "status",
    "command": { // The current command object being run, null if idle
        "type": "move", // The command type
        // A set of parameters, as defined by the command
        "distance": 1
    }
}
```

#### `"option"`: Sets or gets options
Driver → Base → Rover \
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
Driver ← Base ← Rover \
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

#### `"sensor_data"`: Reports sensor values
Driver ← Base ← Rover \
Response: none
```js
{
    "type": "sensor_data",
    "time": 1600896055730369100, // Unix timestamp, in nanoseconds
    "sensor": "imu",
    "measurements": { // The values of each sensor reported
        "x_accel": 3.2, // A specific value of the sensor (passed to Influx as a field)
        ...
    }
}
```

#### `"query_base"`: Gets a value from the base station
Driver → Base \
Response: `"query_base_response"`
```js
{
    "type": "query_base",
    "query": "client_list"
}
```

#### `"query_base_response"`: Returns a value from the base station to the driver
Driver ← Base \
Response: none
```js
{
    "type": "query_base_response",
    "query": "client_list",
    "value": // Any object
}
```

#### `"auth"`: Handles authentication
Driver → Base ← Rover \
Response: `"auth_response"` followed by disconnect if unsuccessful
```js
{
    "type": "auth",
    "token": "<token>"
}
```

#### `"auth_response"`: Notifies if authentication succeeded
Driver ← Base → Rover \
Response: none
```js
{
    "type": "auth_response",
    "success": true,
    "user": "rover" // username
}
```

### Periodic messages 
These messages are sent automatically with a frequency configurable with the options message.
- `"status"` (Base ← Rover)
- `"sensors"` (Base ← Rover)

## On-rover protocol (Raspberry Pi ↔ Arduino)
Serial-based protocol for communicating between RPi and Arduino. \
TODO: define protocol

## User authentication "database": `users.json`
This file simply contains a list of user secret tokens and usernames.
```js
{
    "<TOKEN>": "sandshark",
    "<TOKEN>": "driver1"
}
```