import * as config from "./modules/config.js";
import * as ui from "./modules/ui.js"
import {initLogger, log} from "./modules/logger.js";

let socket;

async function onConnect(ev) {
    let token;
    do {
        token = window.prompt("Please enter your token","");
    } while (!token)

}

async function onMessage(ev) { //TODO
}

async function onDisconnect(ev) { //TODO
}

async function onError(ev) { //TODO
}

function onPageLoad() {
    initLogger([ui.writeToConsole], [broadcastLog])
    ui.initUi();

    socket = new WebSocket(`ws://${config.WS_ADDRESS}:${config.WS_PORT}/driver`);
    socket.onopen = onConnect;
    socket.onmessage = onMessage;
    socket.onclose = onDisconnect;
    socket.onerror = onError;
}

function broadcastLog(message, level) { // TODO

}

window.addEventListener("DOMContentLoaded", onPageLoad, false);

window.addEventListener("unload", function() {
    socket.close();
}, false);