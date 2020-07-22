let socket;

let consoleLines = [];

function updateConsole() {
    let consoleDiv = document.getElementById("consolelines");
    while (consoleDiv.firstChild) {
        consoleDiv.removeChild(consoleDiv.firstChild);
    }
    consoleLines.forEach(function(line) {
        let newParagraph = document.createElement("p");
        let newNode = document.createTextNode(line);
        newParagraph.append(newNode);
        consoleDiv.append(newParagraph)
    });
}

function writeToConsole(message) {
    consoleLines.unshift(message);
    updateConsole();
}

/**
 * Logs a message to the console and broadcasts it to the base station if desired
 *
 * @param {string} message The message to log
 * @param {string} level The log severity, one of [debug, info, warning, error, critical]
 * @param {boolean} broadcast
 */
function log(message, level, broadcast) {
    let formattedMessage = "[" + level.toUpperCase() + "] " + message;
    console.log(formattedMessage);
    if (level !== "debug") {
        writeToConsole(message);
    }
    if (broadcast) {
        //TODO
    }
}

function initUi() {
    let moveAmountSlider = document.getElementById("moveAmountSlider");
    let moveAmountNumber = document.getElementById("moveAmountNumber");
    moveAmountNumber.value = moveAmountSlider.value;

    moveAmountSlider.oninput = function () {
        moveAmountNumber.value = this.value;
    };

    moveAmountNumber.oninput = function () {
        moveAmountSlider.value = this.value;
    };

    let moveSpeedSlider = document.getElementById("moveSpeedSlider");
    let moveSpeedNumber = document.getElementById("moveSpeedNumber");
    moveSpeedNumber.value = moveSpeedSlider.value;

    moveSpeedSlider.oninput = function () {
        moveSpeedNumber.value = this.value;
    };

    moveSpeedNumber.oninput = function () {
        moveSpeedSlider.value = this.value;
    };

    let rotateAmountSlider = document.getElementById("rotateAmountSlider");
    let rotateAmountNumber = document.getElementById("rotateAmountNumber");
    rotateAmountNumber.value = rotateAmountSlider.value;

    rotateAmountSlider.oninput = function () {
        rotateAmountNumber.value = this.value;
        document.getElementById("compass").style.transform = "rotate(" + rotateAmountSlider.value + "deg)";
    };

    rotateAmountNumber.oninput = function () {
        rotateAmountSlider.value = this.value;
    };

    let rotateSpeedSlider = document.getElementById("rotateSpeedSlider");
    let rotateSpeedNumber = document.getElementById("rotateSpeedNumber");
    rotateSpeedNumber.value = rotateSpeedSlider.value;

    rotateSpeedSlider.oninput = function () {
        rotateSpeedNumber.value = this.value;
    };

    rotateSpeedNumber.oninput = function () {
        rotateSpeedSlider.value = this.value;
    };

    let consoleInput = document.getElementById("consoleinput").children.item(0);
    consoleInput.onkeypress = function(e) {
        let keyCode = e.which;
        if (keyCode === 13){
          // Enter pressed
          writeToConsole(this.value);
          this.value = '';
        }
    }
}

function onSocketReady() {
    log("Connected to " + socket.url, "info", false);
}

/**
 * Verify that a message has the correct parameters for its type
 *
 * @param {Object} message The message to verify
 * @return {boolean} Whether the message passed verification
 */
function verifyMsg(message) {
    let keys = Object.keys(message);
    let types = {};
    keys.forEach(function (key) {
        types[key] = typeof key;
    });
    if (!message["type"]) {
        return false;
    }
    if (message["type"] === "log") {
        return types["message"] === "string" && types["level"] === "string";
    }
    // TODO
}

function onMessage(event) {
    let rawMessage = event.data;
    try {
        let msg = JSON.parse(rawMessage);
        if (!verifyMsg(msg)) {
            log("Message failed verification", "error", true);
            console.log(msg);
            return;
        }
        if (msg["type"] === "log") {
            log(msg["message"], msg["level"], false);
        }
    }
    catch (e) {
        log("Received a message with malformed json", "error", true);
        throw e
    }
}

function connect() {
    socket = new WebSocket("ws://localhost:11571/driver");
    socket.onerror = async function (ev) {
        socket.close();
    };
    socket.onclose = async function (ev) {
        log("Socket connection closed", "warning", false);
        //Sleep 5 seconds
        await new Promise(r => setTimeout(r, 5000));
        connect();
    };
    socket.onopen = onSocketReady;
    socket.onmessage = onMessage;
}

function estop() {alert("stop stop STOP!!!");}

window.addEventListener("DOMContentLoaded", async function() {
    initUi();
    connect()
}, false);