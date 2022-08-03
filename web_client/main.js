import * as config from "./modules/config.js";
import * as ui from "./modules/ui.js"
import {initLogger, log} from "./modules/logger.js";
import {USE_WSS} from "./modules/config.js";

let socket;
let authenticated = false;

async function onConnect(ev) {
    let token;
    do {
        token = window.prompt("Please enter your token","");
    } while (!token)
    sendObject({"type": "auth", "token": token})
}

async function onMessage(ev) {
    let raw_msg = ev.data;
    log(raw_msg, "debug");

    let msg
    try {
        msg = JSON.parse(raw_msg);
    } catch (e) {
        log("Error parsing message: " + raw_msg, "error")
        return;
    }

    msg.getOrError = function(property) {
        let res = this[property]
        if (res === undefined) {
            throw "Could not get message property: " + property;
        } else {
            return res;
        }
    }

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
    log('Socket encountered error: ' + ev.message, "error");
    socket.close();
}

function connect() {
    socket = new WebSocket(`${USE_WSS ? 'wss' : 'ws'}://${config.WS_ADDRESS}:${config.WS_PORT}/driver`);
    socket.onopen = onConnect;
    socket.onmessage = onMessage;
    socket.onclose = onDisconnect;
    socket.onerror = onError;
}

function onPageLoad() {
    initLogger([ui.writeToConsole], [broadcastLog])
    ui.initUi();
    ui.registerConsoleCallback(sendMessage);
    connect()
}

function sendMessage(msg) {
    if (socket.readyState !== WebSocket.OPEN) {
        log("Failed to send message because socket is closed", "error");
        return;
    }

    socket.send(msg);
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

// Message Handlers
function handleAuthResponse(success, user) {
    if (success) {
        log("Authentication successful", "info");
    } else {
        log("Authentication failed", "info");
    }

    authenticated = Boolean(success)
}

function handleLog(message, level) {
    log(message, level);
}

function handleCommandEnded(command, completed) {

}

function handleCommandStatus(command) {

}

function handleOptionResponse(values) {

}

function handleSensorData(time, sensor, measurements) {

}

function handleQueryBaseResponse(query, value) {

}

window.addEventListener("DOMContentLoaded", onPageLoad, false);

window.addEventListener("unload", function() {
    socket.close();
}, false);