

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

export function writeToConsole(message) {
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
    minimap.dragging.enable();
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

    attitude_indicator = $.flightIndicator('#attitude', 'attitude', {size: document.getElementById("attitude").clientWidth, showBox: false, img_directory: "libraries/flight_indicators_plugin/img/"});

    let increment = 0;
    setInterval(function() {
        // Attitude update
        updateOrientation(30*Math.sin(increment/10), 50*Math.sin(increment/20), 180 * Math.sin(increment/10))
        increment++;
    }, 50);
}

function updateOrientation(roll, pitch, yaw) {
    attitude_indicator.setRoll(roll);
    attitude_indicator.setPitch(pitch);
    mapMarker.setRotationAngle(yaw);
}

export { initUi }