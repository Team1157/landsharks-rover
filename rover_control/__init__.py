import asyncio
import enum
import json
import os
import pathlib
import subprocess
import time
import typing as t
import traceback
import re

import serde.exceptions
import websockets
import psutil
import serial
import serial_asyncio
import pynmea2
# import RPi.GPIO as GPIO
from common import *

# IR_PIN = 17


class CameraSource(enum.Enum):
    PRETTICAM = "/dev/video0"
    NAVICAM = "/dev/video1"


class Sandshark:
    def __init__(self):
        self.sck: t.Optional[websockets.WebSocketClientProtocol] = None
        self.current_command: t.Optional[Command] = None
        self.user: t.Optional[str] = None
        self.serial_connected: bool = False
        self.serial_reader: t.Optional[asyncio.StreamReader] = None
        self.serial_writer: t.Optional[asyncio.StreamWriter] = None
        self.stream_subprocess = None

        self.camera_yaw = 0
        self.camera_pitch = 90

        self.lastHeartbeat = time.time_ns()

        self.options = {
            "camera.source": None,
            "camera.resolution": (256, 144),
            "camera.framerate": 10,
        }

        self.module_path = pathlib.Path(os.path.dirname(__file__))

        # GPIO.setmode(GPIO.BOARD)
        # GPIO.setup(IR_PIN, GPIO.OUT)

    async def log(self, msg: str, level: str = "info"):
        """Logs a message to the base station if connected"""
        if self.sck and self.sck.open:
            await self.sck.send_msg(LogMessage(message=msg, level=level))

    async def report_pi_sensors_task(self):
        while True:
            if self.sck and self.sck.open:
                # Get various pi stat values
                ram = psutil.virtual_memory()
                disk = psutil.disk_usage("/")
                this_proc = psutil.Process(os.getpid())
                meas = {
                    "cpu_percent": psutil.cpu_percent(),
                    "ram_percent": ram.percent,
                    "ram_free": ram.available,
                    "disk_percent": disk.percent,
                    "disk_free": disk.free,
                    "ctl_ram_used": this_proc.memory_full_info().uss
                }
                if hasattr(psutil, "sensors_temperatures"):
                    meas["cpu_temp"] = psutil.sensors_temperatures()["cpu_thermal"][0].current
                await self.sck.send_msg(SensorDataMessage(time=time.time_ns(), sensor="pi", measurements=meas))
            await asyncio.sleep(5)

    async def main(self):
        print("Rover starting!")

        # Start sensor tasks
        asyncio.create_task(self.report_pi_sensors_task())

        # Start serial listener
        asyncio.create_task(self.serial_main())

        # Start GPS listener
        asyncio.create_task(self.gps_main())

        # Start serial heartbeat
        asyncio.create_task(self.serial_heartbeat())

        with open(self.module_path / "secrets.json") as secrets_file:
            token = json.load(secrets_file)["token"]

        async for self.sck in websockets.connect("wss://rover.team1157.org:11571/rover", ping_interval=5, ping_timeout=10):
        # async for self.sck in websockets.connect("ws://127.0.0.1:11571/rover", ping_interval=5, ping_timeout=10):
            # Authenticate
            await self.sck.send_msg(AuthMessage(token=token))
            try:
                auth_response = AuthResponseMessage.from_json(await self.sck.recv())
                self.user = auth_response.user
            except (serde.ValidationError, json.JSONDecodeError):
                await self.log("Received invalid auth response", "error")
                await self.sck.close(1002, "Invalid auth response")
                continue

            try:
                print("Connected to base station")
                while True:
                    try:
                        async for msg_raw in self.sck:
                            try:
                                msg = Message.from_json(msg_raw)
                            except (serde.ValidationError, json.JSONDecodeError):
                                await self.log("Received invalid message", "error")
                                continue

                            # Delegate to message handler
                            await message_handlers.get(msg.__class__, default_handler)(self, msg)

                    except Exception as e:
                        # Re-raise ConnectionClosed
                        if isinstance(e, websockets.ConnectionClosed):
                            raise e

                        print(f"Uncaught exception in main(): {e!r}")
                        await self.log(f"Rover error in main(): {e!r}: {traceback.format_exc()}", "error")

            except websockets.ConnectionClosed:
                print("Disconnected from base station, reconnecting in 5 seconds...")
                # Cancel command if running
                if self.current_command is not None:
                    if self.serial_connected:
                        print("Cancelling command")
                        self.serial_writer.write(b"x\n")
                        await self.serial_writer.drain()
                    else:
                        print("Unable to cancel command, serial disconnected")
                await asyncio.sleep(5)
                continue

    async def serial_main(self):
        while True:
            try:
                self.serial_reader, self.serial_writer = await serial_asyncio.open_serial_connection(
                    url="/dev/ttyS0",
                    baudrate=115200
                )
                self.serial_connected = True

                while True:
                    try:
                        msg = (await self.serial_reader.readline()).decode()
                        msg_type = msg.strip().split(" ")[0]

                        # Delegate to message handler
                        await arduino_handlers.get(msg_type, arduino_default)(self, msg)

                    except Exception as e:
                        # Re-raise SerialException
                        if isinstance(e, serial.SerialException):
                            raise e

                        print(f"Uncaught exception in serial_main(): {e!r}: {traceback.format_exc()}")
                        await self.log(f"Rover error in serial_main(): {e!r}: {traceback.format_exc()}", "error")
            except serial.SerialException:
                self.serial_connected = False
                print("Disconnected from arduino, reconnecting in 5 seconds...")
                await self.log(f"Disconnected from arduino with error: {traceback.format_exc()}", "error")
                await asyncio.sleep(5)
                continue

    async def serial_heartbeat(self):
        while True:
            if self.serial_connected:
                self.serial_writer.write(b"h\n")
                await self.serial_writer.drain()
            if time.time_ns() - self.lastHeartbeat > 5e9:
                await self.log("Arduino is not replying to heartbeats", "warning")
            await asyncio.sleep(0.5)

    async def gps_main(self):
        # Enable GPS - blocking, since we're still just initializing
        try:
            with serial.Serial("/dev/ttyUSB2", baudrate=115200, rtscts=True, dsrdtr=True) as ser:
                ser.write(b"AT+QGPS=1\r\n")
        except serial.SerialException:
            print("Unable to turn on GPS!")
        print("Turned on GPS")

        await asyncio.sleep(1)
        print("Listening GPS")

        while True:
            try:
                gps_reader, gps_writer = await serial_asyncio.open_serial_connection(
                    url="/dev/ttyUSB1",
                    baudrate=115200,
                    rtscts=True, dsrdtr=True
                )
                while True:
                    try:
                        sentence_raw = (await gps_reader.readline()).decode()
                        # Ignore whitespace-only lines
                        if not sentence_raw.strip():
                            continue

                        ts = time.time_ns()  # system timestamp
                        if self.sck and self.sck.open:
                            # Send raw sentence on an NMEA packet
                            await self.sck.send_msg(NmeaMessage(time=ts, sentence=sentence_raw))
                            # Decode sentence and log as sensor
                            # Only log the values in GGA sentences to avoid duplication by RMC sentences
                            sentence = pynmea2.parse(sentence_raw)
                            if sentence.sentence_type == "GGA" and sentence.is_valid:  # don't report before fix
                                await self.sck.send_msg(SensorDataMessage(
                                    time=ts,
                                    sensor="gps",
                                    measurements={
                                        "time": sentence.timestamp.isoformat(),
                                        "lat": sentence.latitude,
                                        "lon": sentence.longitude,
                                        "alt": sentence.altitude,
                                        "hdop": sentence.horizontal_dil,
                                        "num_sats": int(sentence.num_sats)
                                    }
                                ))

                    except Exception as e:
                        # Re-raise SerialException
                        if isinstance(e, serial.SerialException):
                            raise e

                        print(f"Uncaught exception in gps_main(): {e!r}: {traceback.format_exc()}")
                        await self.log(f"Rover error in gps_main(): {e!r}: {traceback.format_exc()}", "error")

            except serial.SerialException:
                print("Disconnected from GPS, reconnecting in 5 seconds...")
                await self.log(f"Disconnected from GPS with error: {traceback.format_exc()}", "warning")
                await asyncio.sleep(5)
                continue

    def start_stream(self, device: str, width: int, height: int, framerate: int):
        if self.stream_subprocess is not None:
            self.stop_stream()

        script_path = self.module_path.parent / "camera-streamer" / "src" / "target" / "debug" / "camera-streamer"
        self.stream_subprocess = subprocess.Popen([script_path, device, "--resolution", width, height, "--framerate", framerate])

    def stop_stream(self):
        self.stream_subprocess.terminate()
        self.stream_subprocess = None


message_handlers = {}


def message_handler(message_type: t.Type):
    def decorate(fn: t.Callable[[Sandshark, Message], t.Coroutine]):
        message_handlers[message_type] = fn
    return decorate


@message_handler(CommandMessage)
async def handle_command(self: Sandshark, msg: CommandMessage):
    if self.current_command is not None:
        if self.serial_connected:
            self.serial_writer.write(b"x\n")
            await self.serial_writer.drain()
            if self.sck and self.sck.open:
                await self.sck.send_msg(CommandEndedMessage(command=self.current_command, completed=False))
        else:
            await self.log("Could not cancel current command because Arduino is not connected", "error")
    self.current_command = msg.command
    if msg.command is not None:
        if self.serial_connected:
            self.serial_writer.write(self.current_command.to_arduino())
            await self.serial_writer.drain()
            if self.sck and self.sck.open:
                await self.sck.send_msg(CommandStatusMessage(command=self.current_command))
        else:
            await self.log("Could not set command because Arduino is not connected", "error")


@message_handler(OptionMessage)
async def handle_option(self: Sandshark, msg: OptionMessage):
    # Set values
    old_options = self.options.copy()

    if "camera.source" in msg.set.keys:
        source_raw = msg.set.keys["camera.source"]

        if source_raw is None:
            self.options["camera.source"] = None
        else:
            if type(source_raw) is not str:
                await self.log("Option camera.source must be a string or null", "error")
                return

            if source_raw.lower() in ("p", "pretticam", "prettycam"):
                self.options["camera.source"] = CameraSource.PRETTICAM
            elif source_raw.lower() in ("n", "navicam", "navcam"):
                self.options["camera.source"] = CameraSource.NAVICAM
            else:
                await self.log(f"Unknown camera.source: {source_raw}", "error")

    if "camera.resolution" in msg.set.keys:
        resolution_raw = msg.set.keys["camera.resolution"]
        if type(resolution_raw) is not list or len(resolution_raw) != 2 or type(resolution_raw[0]) is not int or type(resolution_raw[1]) is not int:
            await self.log("Option camera.resolution must be an array of two integers", "error")
            return

        self.options["camera.resolution"] = tuple(resolution_raw)

    if "camera.framerate" in msg.set.keys:
        framerate_raw = msg.set.keys["camera.framerate"]
        if type(framerate_raw) is not int:
            await self.log("Option camera.framerate must be an int", "error")
            return

        self.options["camera.framerate"] = framerate_raw

    if any([self.options[k] != old_options[k] for k in self.options.keys()]):
        self.start_stream(
            self.options["camera.source"].value if self.options["camera.source"] is not None else None,
            self.options["camera.resolution"][0],
            self.options["camera.resolution"][1],
            self.options["camera.framerate"]
        )

    # Get values
    if self.sck and self.sck.open:
        await self.sck.send_msg(OptionResponseMessage(
            values={k: self.options[k] for k in set(msg.set.keys()).union(msg.get)}
        ))


@message_handler(EStopMessage)
async def handle_estop(self: Sandshark, _msg: EStopMessage):
    # Forward E-stop
    if self.serial_connected:
        self.serial_writer.write(b"!\n")
        await self.serial_writer.drain()
    else:
        await self.log("Could not handle E-stop because Arduino is not connected", "error")

    if self.current_command is not None:
        if self.sck and self.sck.open:
            await self.sck.send_msg(CommandEndedMessage(command=self.current_command, completed=False))
        self.current_command = None


@message_handler(PointCameraMessage)
async def handle_point_camera(self: Sandshark, msg: PointCameraMessage):
    if msg.relative:
        self.camera_yaw += msg.yaw
        self.camera_pitch += msg.pitch
    else:
        self.camera_yaw = msg.yaw
        self.camera_pitch = msg.pitch

    self.camera_yaw %= 360
    self.camera_pitch = min(max(self.camera_pitch, 0), 100)

    if self.serial_connected:
        self.serial_writer.write(f"p{self.camera_yaw} {self.camera_pitch}".encode())
        await self.serial_writer.drain()
    else:
        await self.log("Unable to point camera because Arduino disconnected", "error")


@message_handler(ArduinoDebugMessage)
async def handle_arduino_debug(self: Sandshark, msg: ArduinoDebugMessage):
    # Send to arduino as raw
    if self.serial_connected:
        self.serial_writer.write(msg.message.encode() + b"\n")
        await self.serial_writer.drain()
    else:
        await self.log("Unable to send debug because Arduino disconnected", "error")


async def default_handler(self: Sandshark, msg: Message):
    if self.sck and self.sck.open:
        await self.sck.send_msg(LogMessage(message=f"Received unexpected {msg.tag_name} message", level="warning"))


arduino_handlers = {}


def arduino_handler(message_type: str):
    def decorate(fn: t.Callable[[Sandshark, str], t.Coroutine]):
        arduino_handlers[message_type] = fn
    return decorate


@arduino_handler("hb")
async def arduino_heartbeat(self: Sandshark, _msg: str):
    self.lastHeartbeat = time.time_ns()


@arduino_handler("echo")
async def arduino_echo(self: Sandshark, msg: str):
    # Log echo
    m = re.match(r"^echo (.*)$", msg)
    await self.log(f"Received echo from Arduino: {m[1]}", "info")


@arduino_handler("log")
async def arduino_log(self: Sandshark, msg: str):
    # Echo log to network
    m = re.match(r"^log (\w+) (.*)$", msg)
    await self.log(f"Arduino: {m[2]}", m[1])


@arduino_handler("completed")
async def arduino_completed(self: Sandshark, _msg: str):
    # Alert network of command completion
    if self.sck and self.sck.open:
        self.sck.send_msg(CommandEndedMessage(command=self.current_command, completed=True))
    self.current_command = None


def float_or_none(x: str) -> t.Optional[float]:
    try:
        return float(x)
    except ValueError:
        return None


def int_or_none(x: str) -> t.Optional[int]:
    try:
        return int(x)
    except ValueError:
        return None


@arduino_handler("data")
async def arduino_data(self: Sandshark, msg: str):
    if self.sck and self.sck.open:
        time_ = time.time_ns()
        m = re.match(r"^data (\w+) (.*)$", msg)
        raw_meas = m[2].strip().split(" ")
        if m[1] in ("internal_bme", "external_bme"):
            meas = {
                "temp": float_or_none(raw_meas[0]),
                "humidity": float_or_none(raw_meas[1]),
                "pressure": int_or_none(raw_meas[2])
            }

        elif m[1] == "imu":
            meas = {
                "roll": float_or_none(raw_meas[0]),
                "pitch": float_or_none(raw_meas[1]),
                "yaw": float_or_none(raw_meas[2]),
                "temp": int_or_none(raw_meas[3])
            }

        elif m[1] == "load_current":
            int_current = int_or_none(raw_meas[0])
            meas = {
                "current":  None if int_current is None else int_current / 10  # deciamps to amps
            }

        elif m[1] == "panel_power":
            meas = {
                "voltage": float_or_none(raw_meas[0]),
                "current": float_or_none(raw_meas[1])
            }

        else:
            await self.log(f"Received unknown sensor data from Arduino: {m[1]}", "error")
            return

        await self.sck.send_msg(SensorDataMessage(
            time=time_,
            sensor=m[1],
            measurements=meas
        ))


async def arduino_default(self: Sandshark, msg: str):
    if self.sck and self.sck.open:
        await self.sck.send_msg(LogMessage(message=f"Received unexpected message from Arduino: {msg}", level="error"))
