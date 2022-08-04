import * as config from "./modules/config.js";
import * as ui from "./modules/ui.js"
import {initLogger, log} from "./modules/logger.js";
import {USE_WSS} from "./modules/config.js";
import {updateOrientation, updatePosition} from "./modules/ui.js";

let msg_socket;
let stream_socket;
let authenticated = false;

async function onConnect(ev) {
    let token;
    do {
        token = window.prompt("Please enter your token","");
    } while (!token)
    sendObject({"type": "auth", "token": token})
}

function getOrError(property) {
    let res = this[property]
    if (res === undefined) {
        log("Failed to read message property: " + property, "error");
        throw "Could not get message property: " + property;
    } else {
        return res;
    }
}

async function onMessage(ev) {
    let raw_msg = ev.data;
    log("Received: " + raw_msg, "debug");

    let msg
    try {
        msg = JSON.parse(raw_msg);
    } catch (e) {
        log("Error parsing message: " + raw_msg, "error")
        return;
    }

    msg.getOrError = getOrError;

    let msg_type = msg.getOrError("type");


    switch (msg_type) {
        case "auth_response":
            handleAuthResponse(msg.getOrError("success"), msg.getOrError("user"));
            break;

        case "log":
            handleLog(msg.getOrError("message"), msg.getOrError("level"));
            break;

        case "command_ended":
            handleCommandEnded(msg.getOrError("command"), msg.getOrError("completed"));
            break;

        case "command_status":
            handleCommandStatus(msg.getOrError("command"));
            break;

        case "option_response":
            handleOptionResponse(msg.getOrError("values"));
            break;

        case "sensor_data":
            handleSensorData(msg.getOrError("time"), msg.getOrError("sensor"), msg.getOrError("measurements"));
            break;

        case "query_base_response":
            handleQueryBaseResponse(msg.getOrError("query"), msg.getOrError("value"));
            break;

        default:
            log("Message has unknown type: " + raw_msg, "error");
    }
}

async function onDisconnect(ev) {
    log("Socket closed", "info");
    if (authenticated) {
        connect();
    }
}

async function onError(ev) {
    log("Socket encountered an error", "error");
    msg_socket.close();
}

function connect() {
    msg_socket = new WebSocket(`${USE_WSS ? 'wss' : 'ws'}://${config.WS_ADDRESS}:${config.WS_MSG_PORT}/driver`);
    msg_socket.onopen = onConnect;
    msg_socket.onmessage = onMessage;
    msg_socket.onclose = onDisconnect;
    msg_socket.onerror = onError;
}

function onPageLoad() {
    initLogger([ui.writeToConsole], [broadcastLog])
    ui.initUi();

    ui.registerConsoleCallback(sendMessage);
    ui.registerDriveCallback(driveCommandCallback);
    ui.registerEStopCallback(eStopCallback);

    connect();
}

function sendMessage(msg) {
    if (msg_socket.readyState !== WebSocket.OPEN) {
        log("Failed to send message because socket is closed", "error");
        return;
    }

    log("Sending: " + msg, "debug");

    msg_socket.send(msg);
}

function sendObject(obj) {
    if (!authenticated && obj.type !== "auth") {
        log("Failed to send message because authentication is not complete", "error")
        return;
    }

    sendMessage(JSON.stringify(obj))
}

function broadcastLog(message, level) {
    sendObject({"type": "log", "message": message, "level": level});
}

function driveCommandCallback(dist, spd, angle) {
    sendObject({
        "type": "command",
        "command": {
            "type": "move_distance",
            "distance": Number(dist),
            "speed": Number(spd),
            "angle": Number(angle)
        }
    });
}

function eStopCallback() {
    sendObject({
        "type": "e_stop"
    });
}

// Message Handlers
function handleAuthResponse(success, user) {
    if (success) {
        log("Authentication successful", "info");
        connectToStream();
    } else {
        log("Authentication failed", "info");
    }

    authenticated = Boolean(success)
}

function handleLog(message, level) {
    log(message, level);
}

function handleCommandEnded(command, completed) {
    if (completed) {
        log("Command completed", "info");
    } else {
        log("Command interrupted", "info");
    }
}

function handleCommandStatus(command) {
    log("Command running", "info");
}

function handleOptionResponse(values) {
    //TODO
}

function handleSensorData(time, sensor, meas) {
    meas.getOrError = getOrError;

    switch (sensor) {
        case "gps":
            updatePosition(meas.getOrError("lat"), meas.getOrError("lon"));
            break;

        case "imu":
            updateOrientation(meas.getOrError("roll"), meas.getOrError("pitch"), meas.getOrError("yaw"));
            document.getElementById("imutemp").innerText = meas.getOrError("temp") + "°C";
            break;

        case "external_bme":
            document.getElementById("exttemp").innerText = meas.getOrError("temp") + "°C";
            document.getElementById("exthumidity").innerText = meas.getOrError("humidity") + "%";
            document.getElementById("extpressure").innerText = (meas.getOrError("pressure") / 100).toFixed(0) + "hPa";
            break;

        case "internal_bme":
            document.getElementById("enclosuretemp").innerText = meas.getOrError("temp") + "°C";
            break;

        case "panel_power":
            document.getElementById("batvoltage").innerText = meas.getOrError("voltage") + "V";
            document.getElementById("panelcurrent").innerText = meas.getOrError("current") + "A";
            break;

        case "load_current":
            document.getElementById("loadcurrent").innerText = meas.getOrError("current") + "A";
            break;

        case "pi":
            document.getElementById("pitemp").innerText = meas.getOrError("cpu_temp") + "°C";
            break;
    }
}

function handleQueryBaseResponse(query, value) {
    // TODO
    log("Base station responded to query " + toString(query) + "with value " + toString(value), "info")
}

function connectToStream() {
    stream_socket = new WebSocket(`${USE_WSS ? 'wss' : 'ws'}://${config.WS_ADDRESS}:${config.WS_STREAM_PORT}`);

    stream_socket.onopen = function (_ev) {
        log("Connected to stream socket", "info");
    }

    stream_socket.onmessage = function (ev) {
        ui.onFrame(ev.data);
    }

    stream_socket.onerror = function (_ev) {
        log("Streaming socket encountered an error", "error");
        stream_socket.close();
    }

    stream_socket.onclose = function (_ev) {
        log("Streaming socket closed", "info");
        setTimeout(function () {
          connectToStream();
        }, 5000)
    }
}

window.addEventListener("DOMContentLoaded", onPageLoad, false);

window.addEventListener("unload", function() {
    msg_socket.close();
}, false);