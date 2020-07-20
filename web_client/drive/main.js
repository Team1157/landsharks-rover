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
}

function onMessage(event) {
    console.log(event.data)
}

function estop() {alert("stop stop STOP!!!");}

window.addEventListener("DOMContentLoaded", function() {
    initUi();
    let socket = new WebSocket("ws://localhost:11571");

    console.log(socket.readyState);
}, false);