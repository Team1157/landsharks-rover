import asyncio
import json
import os
import time
import typing as t
import traceback

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

        self.options = {
            "navicam.enabled": False,
            "prettycam.enabled": False,

        }

    async def report_pi_sensors_task(self):
        while True:
            if self.sck is not None and self.sck.open:
                # Get various pi stat values
                ram = psutil.virtual_memory()
                disk = psutil.disk_usage("/")
                this_proc = psutil.Process(os.getpid())
                await self.sck.send_msg(SensorDataMessage(time=time.time_ns(), sensor="pi", measurements={
                    "cpu_percent": psutil.cpu_percent(),
                    "ram_percent": ram.percent,
                    "ram_free": ram.available,
                    "disk_percent": disk.percent,
                    "disk_free": disk.free,
                    "ctl_ram_used": this_proc.memory_full_info().uss
                }))
            await asyncio.sleep(5)

    async def main(self):
        print("Rover starting!")

        # Start sensor tasks
        asyncio.create_task(self.report_pi_sensors_task())

        # Start serial listener
        asyncio.create_task(self.serial_main())

        # async for sck in websockets.connect("ws://rover.team1157.org:11571/rover", ping_interval=5, ping_timeout=10):
        async for self.sck in websockets.connect("ws://127.0.0.1:11571/rover", ping_interval=5, ping_timeout=10):
            # Authenticate
            await self.sck.send_msg(AuthMessage(token="DUMMY_TOKEN"))
            try:
                auth_response = AuthResponseMessage.from_json(await self.sck.recv())
                self.user = auth_response.user
            except (serde.ValidationError, json.JSONDecodeError):
                await self.sck.send_msg(LogMessage(message="Received invalid auth response", level="error"))
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
                                await self.sck.send_msg(LogMessage(message="Received invalid message", level="error"))
                                continue

                            # Delegate to message handler
                            await message_handlers.get(msg.__class__, default_handler)(self, msg)
                    except Exception as e:
                        # Re-raise ConnectionClosed
                        if isinstance(e, websockets.ConnectionClosed):
                            raise e

                        print(f"Uncaught exception in main(): {e!r}")
                        if self.sck.open:
                            await self.sck.send_msg(LogMessage(
                                message=f"Rover error in main(): {e!r}: {traceback.format_exc()}",
                                level="error"
                            ))

            except websockets.ConnectionClosed:
                print("Disconnected from base station, reconnecting in 5 seconds...")
                await asyncio.sleep(5)
                continue

    async def serial_main(self):
        while True:
            try:
                self.serial_reader, self.serial_writer = await serial_asyncio.open_serial_connection(url="COM5", baudrate=115200)
                self.serial_connected = True

                while True:
                    try:
                        line = await self.serial_reader.readline()
                        print(line)
                    except Exception as e:
                        # Re-raise SerialException
                        if isinstance(e, serial.SerialException):
                            raise e

                        print(f"Uncaught exception in serial_main(): {e!r}")
                        if self.sck.open:
                            await self.sck.send_msg(LogMessage(
                                message=f"Rover error in serial_main(): {e!r}: {traceback.format_exc()}",
                                level="error"
                            ))
            except serial.SerialException:
                self.serial_connected = False
                print("Disconnected from arduino, reconnecting in 5 seconds...")
                if self.sck.open:
                    await self.sck.send_msg(LogMessage(
                        message=f"Disconnected from arduino with error: {traceback.format_exc()}",
                        level="error"
                    ))
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
        # TODO cancel command
        if self.sck.open:
            await self.sck.send_msg(CommandEndedMessage(command=self.current_command), completed=False)
    self.current_command = msg.command
    if msg.command is not None:
        if self.serial_connected:
            self.serial_writer.write(self.current_command.to_arduino())
        elif self.sck.open:
            await self.sck.send_msg(LogMessage(
                message="Could not set command because Arduino is not connected",
                level="error"
            ))


@message_handler(OptionMessage)
async def handle_option(self: Sandshark, msg: OptionMessage):
    # Set values
    self.options.update(msg.set)

    # Get values
    await self.sck.send_msg(OptionResponseMessage(
        values={k: self.options[k] for k in set(msg.set.keys()).union(msg.get)}
    ))


@message_handler(EStopMessage)
async def handle_estop(self: Sandshark, msg: EStopMessage):
    # TODO
    pass


@message_handler(PointCameraMessage)
async def handle_point_camera(self: Sandshark, msg: PointCameraMessage):
    # TODO
    pass


async def default_handler(self: Sandshark, msg: Message):
    await self.sck.send_msg(LogMessage(message=f"Received unexpected {msg.tag_name} message", level="warning"))


command_handlers = {}


def command_handler(command_type: t.Type):
    def decorate(fn: t.Callable[[Sandshark, Command], t.Coroutine]):
        command_handlers[command_type] = fn
    return decorate


@command_handler(MoveDistanceCommand)
async def move_distance_command(self: Sandshark, cmd: MoveDistanceCommand):
    pass


def collect_sensors():
    _dummy = 0.0
    # Get various pi stat values
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    # psutil.sensors_temperatures only exists on Linux
    if "sensors_temperatures" in psutil.__all__:
        cpu_temp = psutil.sensors_temperatures()["coretemp"][0].current
    else:
        cpu_temp = _dummy
    this_proc = psutil.Process(os.getpid())
    return {
        "pi": {
            "cpu_percent": psutil.cpu_percent(),
            "cpu_temp": cpu_temp,
            "ram_percent": ram.percent,
            "ram_free": ram.available,
            "disk_percent": disk.percent,
            "disk_free": disk.free,
            "ctl_ram_used": this_proc.memory_full_info().uss
        },
        "gps": {
            "latitude": _dummy,
            "longitude": _dummy,
            "satellites": _dummy
        },
        "imu": {
            "gyro_x": _dummy,
            "gyro_y": _dummy,
            "gyro_z": _dummy,
            "acc_x": _dummy,
            "acc_y": _dummy,
            "acc_z": _dummy,
            "mag_x": _dummy,
            "mag_y": _dummy,
            "mag_z": _dummy
        },
        "battery": {
            "voltage": _dummy,
            "current": _dummy
        }
    }
