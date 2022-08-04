

let consoleLines = [];

let positionKnown = false;
let roverPos;
let attitude_indicator;
let minimap;
let mapMarker;

let consoleMessageCallback;
let driveMessageCallback;
let eStopCallback;

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

export function registerConsoleCallback(callback) {
    consoleMessageCallback = callback;
}

export function registerDriveCallback(callback) {
    driveMessageCallback = callback;
}

export function registerEStopCallback(callback) {
    eStopCallback = callback;
}

export function writeToConsole(message, level) {
    if (level === "debug") {
        return;
    }

    if (level === undefined) {
        consoleLines.push(message);
    } else {
        consoleLines.push("[" + level + "] " + message);
    }

    updateConsole();
}

export function initUi() {
    // Setup sliders
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

    // Setup move buttons
    document.getElementById("tul").onclick = function (e) {
        driveMessageCallback(moveAmountNumber.value, moveSpeedNumber.value, -rotateAmountNumber.value);
    }

    document.getElementById("tum").onclick = function (e) {
        driveMessageCallback(moveAmountNumber.value, moveSpeedNumber.value, 0);
    }

    document.getElementById("tur").onclick = function (e) {
        driveMessageCallback(moveAmountNumber.value, moveSpeedNumber.value, rotateAmountNumber.value);
    }

    document.getElementById("tml").onclick = function (e) {
        driveMessageCallback(0, moveSpeedNumber.value, -rotateAmountNumber.value);
    }

    document.getElementById("tmm").onclick = function (e) {
        eStopCallback();
    }

    document.getElementById("tmr").onclick = function (e) {
        driveMessageCallback(0, moveSpeedNumber.value, -rotateAmountNumber.value);
    }

    document.getElementById("tbl").onclick = function (e) {
        driveMessageCallback(-moveAmountNumber.value, moveSpeedNumber.value, rotateAmountNumber.value);
    }

    document.getElementById("tbm").onclick = function (e) {
        driveMessageCallback(-moveAmountNumber.value, moveSpeedNumber.value, 0);
    }

    document.getElementById("tbr").onclick = function (e) {
        driveMessageCallback(-moveAmountNumber.value, moveSpeedNumber.value, rotateAmountNumber.value);
    }

    document.onkeydown = function (ev) {
        if (ev.key === ' ') {
            // Don't estop when typing a space in the console
            if (!(ev.target.nodeName.toLowerCase() === "input" && ev.target.type.toLowerCase() === "text")) {
                eStopCallback();
            }
        }
    }

    // Setup console
    let consoleInput = document.getElementById("consoleinput").children.item(0);
    consoleInput.onkeypress = function(e) {
        let keyCode = e.which;

        if (keyCode === 13) {
          // Enter pressed
          writeToConsole("> " + this.value);
          consoleMessageCallback(this.value);
          this.value = '';
        }
    };

    // Setup minimap
    roverPos = null

    minimap = new L.map('mapid', {
        zoom: 11,
        minZoom: 10,
        center: new L.LatLng(39.14780950,-108.48908354),
        attributionControl: false
    });

    L.esri.basemapLayer('Imagery').addTo(minimap);
    L.control.scale().addTo(minimap);
    minimap.dragging.enable();
    minimap.touchZoom.disable();
    minimap.doubleClickZoom.enable();
    minimap.scrollWheelZoom.enable();
    minimap.boxZoom.disable();
    minimap.keyboard.disable();
    document.getElementById('mapid').style.cursor='default';

    let followRoverCheckbox = document.getElementById("followrovercheckbox");
    minimap.on("zoom", function (e) {
        if (followRoverCheckbox.checked && roverPos !== null) {
            minimap.panTo(roverPos);
        }
    });

    followRoverCheckbox.onchange = function (e) {
        if (followRoverCheckbox.checked) {
            if (positionKnown) {
                minimap.dragging.disable();
                minimap.panTo(roverPos);
            }
        } else {
            minimap.dragging.enable();
        }
    };

    let markerIcon = L.icon({
        iconUrl: "images/map_marker.svg",
        iconSize: [30, 30],
        iconAnchor: [15, 15]
    })
    mapMarker = L.marker(L.LatLng(0, 0), {icon: markerIcon})

    let xmlhttp = new XMLHttpRequest();
    xmlhttp.onreadystatechange = function() {
      if (this.readyState === 4 && this.status === 200) {
        L.geoJSON(JSON.parse(this.responseText), {style: {color: "#ff0000", fillOpacity: 0}}).addTo(minimap);
      }
    };
    xmlhttp.open("GET", "assets/ohv_boundaries.geojson", true);
    xmlhttp.send();

    attitude_indicator = $.flightIndicator('#attitude', 'attitude', {size: document.getElementById("attitude").clientWidth, showBox: false, img_directory: "libraries/flight_indicators_plugin/img/"});
}

export function updatePosition(lat, lng) {
    roverPos = new L.LatLng(lat, lng)
    mapMarker.setLatLng(roverPos)

    if (!positionKnown) {
        mapMarker.addTo(minimap);
        minimap.setZoom(18);
    }

    if (document.getElementById("followrovercheckbox").checked || !positionKnown) {
        minimap.panTo(roverPos)
    }

    positionKnown = true;

    document.getElementById("mapcaption").innerText = `${lat.toFixed(6)}, ${lng.toFixed(6)}`
}

export function updateOrientation(roll, pitch, yaw) {
    attitude_indicator.setRoll(roll);
    attitude_indicator.setPitch(pitch);
    mapMarker.setRotationAngle(yaw);
}

export function onFrame(raw_frame) {

}
