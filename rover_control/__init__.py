import asyncio
import json
import os
import time
import typing as t
import traceback
import re

import serde.exceptions
import websockets
import psutil
import serial
import serial_asyncio
from common import *


class Sandshark:
    commands: t.Dict[str, t.Callable[..., t.Coroutine]] = {}

    @classmethod
    def register_command(cls, fn: t.Callable[..., t.Coroutine]):
        cls.commands[fn.__name__] = fn

    def __init__(self):
        self.sck: t.Optional[websockets.WebSocketClientProtocol] = None
        self.current_command: t.Optional[Command] = None
        self.user: t.Optional[str] = None
        self.serial_connected: bool = False
        self.serial_reader: t.Optional[asyncio.StreamReader] = None
        self.serial_writer: t.Optional[asyncio.StreamWriter] = None

        self.camera_yaw = 0
        self.camera_pitch = 0

        self.options = {
            "navicam.enabled": False,
            "prettycam.enabled": False,

        }

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
                    meas["cpu_temp"] = psutil.sensors_temperatures()["coretemp"][0].current
                await self.sck.send_msg(SensorDataMessage(time=time.time_ns(), sensor="pi", measurements=meas))
            await asyncio.sleep(5)

    async def main(self):
        print("Rover starting!")

        # Start sensor tasks
        asyncio.create_task(self.report_pi_sensors_task())

        # Start serial listener
        asyncio.create_task(self.serial_main())

        # async for sck in websockets.connect("wss://rover.team1157.org:11571/rover", ping_interval=5, ping_timeout=10):
        async for self.sck in websockets.connect("ws://127.0.0.1:11571/rover", ping_interval=5, ping_timeout=10):
            # Authenticate
            await self.sck.send_msg(AuthMessage(token="DUMMY_TOKEN"))
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
                await asyncio.sleep(5)
                continue

    async def serial_main(self):
        while True:
            try:
                self.serial_reader, self.serial_writer = await serial_asyncio.open_serial_connection(
                    url="COM5",
                    baudrate=115200
                )
                self.serial_connected = True

                while True:
                    try:
                        msg = await self.serial_reader.readline().decode()
                        msg_type = re.match(r"^(\w+) ", msg)[1]

                        # Delegate to message handler
                        await arduino_handlers.get(msg_type, arduino_default)(self, msg)

                    except Exception as e:
                        # Re-raise SerialException
                        if isinstance(e, serial.SerialException):
                            raise e

                        print(f"Uncaught exception in serial_main(): {e!r}")
                        await self.log(f"Rover error in serial_main(): {e!r}: {traceback.format_exc()}", "error")
            except serial.SerialException:
                self.serial_connected = False
                print("Disconnected from arduino, reconnecting in 5 seconds...")
                await self.log(f"Disconnected from arduino with error: {traceback.format_exc()}", "error")
                await asyncio.sleep(5)
                continue


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
                await self.sck.send_msg(CommandEndedMessage(command=self.current_command), completed=False)
        else:
            await self.log("Could not cancel current command because Arduino is not connected", "error")
    self.current_command = msg.command
    if msg.command is not None:
        if self.serial_connected:
            self.serial_writer.write(self.current_command.to_arduino())
            await self.serial_writer.drain()
        else:
            await self.log("Could not set command because Arduino is not connected", "error")


@message_handler(OptionMessage)
async def handle_option(self: Sandshark, msg: OptionMessage):
    # Set values
    self.options.update(msg.set)

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

    if self.serial_connected:
        self.serial_writer.write(f"p{self.camera_yaw} {self.camera_pitch}".encode())
        await self.serial_writer.drain()
    else:
        await self.log("Unable to point camera because Arduino disconnected", "error")


@message_handler(ArduinoDebugMessage)
async def handle_arduino_debug(self: Sandshark, msg: ArduinoDebugMessage):
    # Send to arduino as raw
    if self.serial_connected:
        self.serial_writer.write(msg.message + b"\n")
        await self.serial_writer.drain()
    else:
        await self.log("Unable to send debug because Arduino disconnected", "error")


async def default_handler(self: Sandshark, msg: Message):
    if self.sck and self.sck.open:
        await self.sck.send_msg(LogMessage(message=f"Received unexpected {msg.tag_name} message", level="warning"))


command_handlers = {}


def command_handler(command_type: t.Type):
    def decorate(fn: t.Callable[[Sandshark, Command], t.Coroutine]):
        command_handlers[command_type] = fn
    return decorate


@command_handler(MoveDistanceCommand)
async def move_distance_command(_self: Sandshark, _cmd: MoveDistanceCommand):
    pass


arduino_handlers = {}


def arduino_handler(message_type: str):
    def decorate(fn: t.Callable[[Sandshark, str], t.Coroutine]):
        arduino_handlers[message_type] = fn
    return decorate


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


@arduino_handler("data")
async def arduino_data(self: Sandshark, msg: str):
    if self.sck and self.sck.open:
        time_ = time.time_ns
        m = re.match(r"^data (\w+) (.*)$", msg)
        raw_meas = m[2].split(" ")
        match m[1]:
            case "internal_bme", "external_bme":
                meas = {
                    "temp": float(raw_meas[0]),
                    "humidity": float(raw_meas[1]),
                    "pressure": int(raw_meas[2])
                }

            case "imu":
                meas = {
                    "x_accel": float(raw_meas[0]),
                    "y_accel": float(raw_meas[1]),
                    "z_accel": float(raw_meas[2]),
                    "roll": float(raw_meas[3]),
                    "pitch": float(raw_meas[4]),
                    "yaw": float(raw_meas[5]),
                    "temp": int(raw_meas[6])
                }

            case "load_current":
                meas = {
                    "current": int(raw_meas[0])
                }

            case "panel_power":
                meas = {
                    "voltage": float(raw_meas[0]),
                    "current": float(raw_meas[1])
                }
            case x:
                await self.log(f"Received unknown sensor data from Arduino: {x}")
                return

        await self.sck.send_msg(SensorDataMessage(
            time=time_,
            sensor=m[1],
            measurements=meas
        ))


async def arduino_default(self: Sandshark, msg: str):
    if self.sck and self.sck.open:
        self.sck.send_msg(LogMessage(message=f"Received unexpected message from Arduino: {msg}", level="error"))
