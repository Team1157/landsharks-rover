let socket;
let connectedRovers =[];
let connectedDrivers = [];

let consoleLines = [];

let roverPos;
let attitude_indicator;
let minimap;
let mapMarker;

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
    while (document.getElementById("consolelines").clientHeight + document.getElementById("consoleprompt").clientHeight > document.getElementById("console").clientHeight) {
        consoleDiv.removeChild(consoleDiv.firstChild);
        consoleLines.shift();
    }
}

function writeToConsole(message) {
    consoleLines.push(message);
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
        if (!socket) {
            this.value = '';
        }
        else if (keyCode === 13) {
          // Enter pressed
          writeToConsole("> " + this.value);
          socket.send(this.value);
          this.value = '';
        }
    };

    //TODO: Remove
    roverPos = new L.LatLng(39.118928, -108.499376)

    minimap = new L.map('mapid', {
        zoom: 17,
        minZoom: 10,
        center: roverPos,
        attributionControl: false
    });
    L.esri.basemapLayer('Imagery').addTo(minimap);
    L.control.scale().addTo(minimap);
    minimap.dragging.disable();
    minimap.touchZoom.disable();
    minimap.doubleClickZoom.disable();
    minimap.scrollWheelZoom.disable();
    minimap.boxZoom.disable();
    minimap.keyboard.disable();
    document.getElementById('mapid').style.cursor='default';
    minimap.on("zoom", function (e) {
        minimap.panTo(roverPos);
    });

    let markerIcon = L.icon({
        iconUrl: "images/map_marker.svg",
        iconSize: [30, 30],
        iconAnchor: [15, 15]
    })
    mapMarker = L.marker(roverPos, {icon: markerIcon, rotationAngle: 180}).addTo(minimap);

    let xmlhttp = new XMLHttpRequest();
    xmlhttp.onreadystatechange = function() {
      if (this.readyState === 4 && this.status === 200) {
        L.geoJSON(JSON.parse(this.responseText), {style: {color: "#ff0000", fillOpacity: 0}}).addTo(minimap);
      }
    };
    xmlhttp.open("GET", "assets/ohv_boundaries.geojson", true);
    xmlhttp.send();

    attitude_indicator = $.flightIndicator('#attitude', 'attitude', {size: 200, showBox: false, img_directory: "libraries/flight_indicators_plugin/img/"});

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
    switch (message["type"]) {
        case "log":
            return types["message"] === "string" && types["level"] === "string";
        case "error":
            return types["error"] === "string" && types["message"] === "string";
        case "query_response":
            return types["query"] === "string" && types["value"] !== undefined;
        default:
            return false
    }
}

function onMessage(event) {
    let rawMessage = event.data;
    log("Received message: " + rawMessage, "debug", false);
    try {
        let msg = JSON.parse(rawMessage);
        if (!verifyMsg(msg)) {
            log("Message from Base failed verification", "error", true);
            console.log(msg);
            return;
        }
        switch (msg["type"]) {
            case "log": {
                log(msg["message"], msg["level"], false);
                break;
            }
            case "error": {
                log("Base error: " + msg["message"], "error", false);
                break;
            }
            case "query_response": {
                switch (msg["query"]) {
                    case "client_list": {
                        let clients = msg["value"];
                        if (typeof clients === "object" && clients["rovers"] !== undefined && clients["drivers"] !== undefined) {
                            connectedRovers = clients["rovers"];
                            connectedDrivers = clients["drivers"];
                            connectedRovers = ["DEBUG ROVER"]; //TODO remove this
                            document.getElementById("noBaseMessage").style.display = "none";
                            if (connectedRovers.length > 0) {
                                document.getElementById("noRoverMessage").style.display = "none";
                                if (document.getElementById("roverUI").style.display === "none") {
                                    document.getElementById("roverUI").style.display = "block";
                                    minimap.invalidateSize();
                                } else {
                                    document.getElementById("roverUI").style.display = "block";
                                }
                            } else {
                                document.getElementById("noRoverMessage").style.display = "block";
                                document.getElementById("roverUI").style.display = "none";
                            }
                        } else {
                            log("Base query response improperly formatted", "error", true)
                        }
                        break;
                    }
                    default:
                        log("Base responded to unknown query", "error", true)
                }
                break;
            }
            default:
                log("Message passed verification, but was not handled", "error", true)
        }
    }
    catch (e) {
        log("Error in message parsing/handling", "error", true);
    }
}

function connect() {
    socket = new WebSocket("ws://localhost:11571/driver");
    socket.onerror = async function (ev) {
        socket.close();
    };
    socket.onclose = async function (ev) {
        log("Socket connection closed", "warning", false);
        document.getElementById("noBaseMessage").style.display = "block";
        document.getElementById("noRoverMessage").style.display = "none";
        document.getElementById("roverUI").style.display = "none";
        // Sleep 5 seconds
        await new Promise(r => setTimeout(r, 5000));
        connect();
    };
    socket.onopen = onSocketReady;
    socket.onmessage = onMessage;
}

function eStop() {
    if (socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({
            "type": "e_stop"
        }));
        log("Sent e-stop!", "debug", false)
    }
}

async function sendQueries() {
    while (true) {
        if (socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({
                "type": "query",
                "query": "client_list"
            }))
        }
        // Sleep 5 seconds
        await new Promise(r => setTimeout(r, 2000));
    }
}

window.addEventListener("DOMContentLoaded", function() {
    initUi();
    connect();
    sendQueries();

    let increment = 0;
    setInterval(function() {
        // Attitude update
        attitude_indicator.setRoll(30*Math.sin(increment/10));
        attitude_indicator.setPitch(50*Math.sin(increment/20));
        mapMarker.setRotationAngle(180 * Math.sin(increment/10));

        increment++;
    }, 50);
}, false);

window.addEventListener("unload", function() {
    socket.close();
}, false);