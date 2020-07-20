import asyncio
import csv
import json
import os
import websockets
import typing as t
import logging
from logging import handlers
import datetime
from common import Msg, Error

# Numeric logging levels as defined by `logging`
LOG_LEVELS = {
    "critical": logging.CRITICAL,
    "fatal": logging.FATAL,
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "warn": logging.WARN,
    "info": logging.INFO,
    "debug": logging.DEBUG
}


def flatten_dict(tree: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
    """
    Takes a multi-level dictionary and flattens it into one layer, with keys representing the path to the value in the
    original dictionary
    :param tree: The dictionary to flatten
    :return: The flattened dictionary
    """
    out = {}
    for key, value in tree.items():
        if type(value) == dict:
            for k, v in flatten_dict(value).items():
                out[f"{key}.{k}"] = v
        else:
            out[key] = value
    return out


class RoverBaseStation:
    def __init__(self):
        self.drivers: t.Set[websockets.WebSocketServerProtocol] = set()
        self.rovers: t.Set[websockets.WebSocketServerProtocol] = set()

        self.command_ids: t.Dict[int, websockets.WebSocketServerProtocol] = {}
        self.command_queue: t.List[t.Dict[str, t.Any]] = []
        self.current_command: t.Optional[t.Dict[str, t.Any]] = None

        # #  LOGGING CONFIGURATION  # #
        # Create logger
        self.logger = logging.getLogger("base_station")
        self.logger.setLevel(logging.DEBUG)
        # Get other loggers to add handlers to, set them to INFO
        ws_log = logging.getLogger("websockets")
        ws_log.setLevel(logging.INFO)
        ws_proto_log = logging.getLogger("websockets.protocol")
        ws_proto_log.setLevel(logging.INFO)
        ws_server_log = logging.getLogger("websockets.server")
        ws_server_log.setLevel(logging.INFO)
        loggers = [
            self.logger,
            ws_log,
            ws_proto_log,
            ws_server_log
        ]
        # Create formatter
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s: %(module)s.%(funcName)s] %(message)s")
        # Stream handler (STDOUT)
        stream_handl = logging.StreamHandler()
        stream_handl.setFormatter(fmt)
        stream_handl.setLevel(logging.DEBUG)
        self.logger.addHandler(stream_handl)
        # File hanlder (logs/base_station.log.<DATE>)
        file_handl = logging.handlers.TimedRotatingFileHandler(
            os.path.join("logs", "base_station.log"),
            when="midnight"
        )
        file_handl.setFormatter(fmt)
        file_handl.setLevel(logging.DEBUG)
        self.logger.addHandler(file_handl)
        # Add handlers to loggers
        for logger in loggers:
            logger.addHandler(stream_handl)
            logger.addHandler(file_handl)

        self.logger.info("Rover base station starting!")

    async def broadcast(self, message: str):
        """
        Broadcasts a message to all connected clients
        :param message: The message to send
        :return:
        """
        clients = self.drivers.union(self.rovers)
        if clients:
            await asyncio.wait([sck.send(message) for sck in clients])

    async def broadcast_drivers(self, message: str):
        """
        Broadcasts a message to all Drivers
        :param message: The message to send
        :return:
        """
        if self.drivers:
            await asyncio.wait([sck.send(message) for sck in self.drivers])

    async def broadcast_rovers(self, message: str):
        """
        Broadcasts a message to all Rovers
        :param message: The message to send
        :return:
        """
        if self.rovers:
            await asyncio.wait([sck.send(message) for sck in self.rovers])

    async def log(self, message: str, level="info"):
        """
        Broadcasts a log message to the connected Drivers and writes to local log
        :param message: The message to send
        :param level: The loglevel or "severity" to indicate (debug, info, warning, error, critical)
        :return:
        """
        if level.lower() in LOG_LEVELS:
            self.logger.log(LOG_LEVELS[level], message)
        else:
            self.logger.warning(f"Invalid logging level: {level}")
            self.logger.warning(message)
        await self.broadcast_drivers(Msg.log(message, level))

    async def register_client(self, sck: websockets.WebSocketServerProtocol, path: str) -> bool:
        """
        Registers a new client connection
        :param sck: The client connection
        :param path: The connection path, used to determine whether the connected client is a Driver or a Rover.
        :return: Whether the client was successfully registered
        """
        if path == "/driver":
            self.drivers.add(sck)
            await self.log(f"New driver connected: {sck.remote_address[0]}")
        elif path == "/rover":
            self.rovers.add(sck)
            if len(self.rovers) > 1:
                await self.log(f"Rover connected while one was already connected: {sck.remote_address[0]}", "warning")
            else:
                await self.log(f"Rover connected: {sck.remote_address[0]}")
        else:
            await self.log(f"Client tried to connect with invalid path: {sck.remote_address[0]}", "warning")
            await sck.close(1008, "Invalid path")
            return False
        return True

    async def unregister_client(self, sck: websockets.WebSocketServerProtocol):
        """
        Unregisters a client connection
        :param sck: The connection
        :return:
        """
        if sck in self.drivers:
            self.drivers.remove(sck)
            await self.log(f"Driver disconnected: {sck.remote_address[0]}")
        elif sck in self.rovers:
            self.drivers.remove(sck)
            await self.log(f"Rover disconnected: {sck.remote_address[0]}")
        else:
            await self.log(f"Client disconnected which was never registered: {sck.remote_address[0]}", "warning")

    async def serve(self, sck: websockets.WebSocketServerProtocol, path: str):
        if not await self.register_client(sck, path):
            return

        data_path: str = os.path.join("sensor_data", f"{datetime.date.today().isoformat()}.csv")

        need_header: bool
        data_file: t.TextIO
        if os.path.exists(data_path):
            data_file = open(data_path, "a", newline='')
            need_header = False
        else:
            data_file = open(data_path, "w", newline='')
            need_header = True

        data_writer: t.Optional[csv.DictWriter] = None
        try:
            async for msg_raw in sck:  # Continually receive messages
                # Decode and verify message
                try:
                    msg = json.loads(msg_raw)
                except json.JSONDecodeError:
                    await sck.send(Msg.error(Error.json_parse_error, "Failed to parse message"))
                    await self.log(f"Received message with malformed JSON from {sck.remote_address[0]}", "error")
                    continue
                if not Msg.verify(msg):
                    await sck.send(Msg.error(Error.invalid_message, "The message sent is invalid"))
                    await self.log(f"Received invalid message from {sck.remote_address[0]}", "error")
                    continue

                if sck in self.drivers:
                    if msg["type"] == "command":
                        # Store command id to route response later
                        if msg["id"] in self.command_ids:
                            await sck.send(Msg.error(Error.id_in_use, "The given command ID is already in use"))
                            continue
                        self.command_ids[msg["id"]] = sck
                        # Put the command in the command queue
                        self.command_queue.append(msg)
                        # Log command
                        await self.log(
                            f"{sck.remote_address} sent command {msg['command']} (#{msg['id']}) "
                            f"with parameters {msg['parameters']} (#{len(self.command_queue)} in queue)"
                        )
                    elif msg["type"] == "clear_queue":
                        while len(self.command_queue) > 0:
                            # Free up the ids of the removed commands
                            cmd = self.command_queue.pop(0)
                            del self.command_ids[cmd["id"]]
                        await self.log(f"Queue cleared by {sck.remote_address[0]}")
                        await self.broadcast_drivers(Msg.queue_status(self.current_command, self.command_queue))
                    elif msg["type"] == "option":
                        self.logger.info(f"{sck.remote_address[0]} getting options {msg['get']!r}, "
                                         f"Setting options {msg['set']!r}")
                        await self.broadcast_rovers(msg)
                    elif msg["type"] == "log":
                        # Route log to drivers
                        await self.log(f"Driver {sck.remote_address[0]} logged: {msg['message']}", msg["level"])
                    elif msg["type"] == "error":
                        await self.log(f"Driver {sck.remote_address[0]} reported error {msg['error']}: "
                                       f"{msg['message']}", "error")
                    elif msg["type"] == "e_stop":
                        await self.broadcast_rovers(msg)
                        await self.log(f"Driver {sck.remote_address[0]} activated e-stop!", "warning")
                    else:
                        await sck.send(Msg.error(Error.invalid_message, "Unknown message type"))
                        await self.log(f"Received message with an unknown type from {sck.remote_address[0]}", "error")

                elif sck in self.rovers:
                    if msg["type"] == "command_response":
                        # Route response to correct driver
                        if msg["id"] not in self.command_ids:
                            await sck.send(Msg.error(Error.unknown_id, "The given command ID is not valid"))
                            await self.log(f"Command response received from rover {sck.remote_address[0]} "
                                           f"with invalid id", "error")
                            continue
                        await self.command_ids[msg["id"]].send(json.dumps(msg))
                        # Log (debug)
                        await self.log(
                            f"{sck.remote_address[0]} sent response (#{msg['id']}) to "
                            f"{self.command_ids[msg['id']].remote_address}"
                        )
                        # Free up command id
                        # May cause issues if more than 1 rover is connected, which shouldn't ever be the case
                        if self.current_command is None or msg["id"] != self.current_command["id"]:
                            await self.log(f"Command response received from {sck.remote_address[0]} "
                                           f"that does not match the running command",
                                           "warning")
                        del self.command_ids[msg["id"]]
                        self.current_command = None
                    elif msg["type"] == "status":
                        status = msg["status"]
                        if status == "busy":
                            pass
                        elif status == "idle":
                            if not len(self.command_queue) == 0:
                                next_command = self.command_queue.pop(0)
                                await self.broadcast_rovers(json.dumps(next_command))
                                await self.log(f"Sent command '{next_command['command']}' "
                                               f"with parameters {next_command['parameters']!r}")
                                self.current_command = next_command
                        else:
                            await self.log(f"Status message received from {sck.remote_address[0]} with an unknown "
                                           f"status: {status}", "error")
                    elif msg["type"] == "option_response":
                        await self.log(f"Option response from {sck.remote_address[0]}: {msg['values']!r}")
                        await self.broadcast_drivers(msg)
                    elif msg["type"] == "digest":
                        flattened_data = flatten_dict(msg)
                        flattened_data["time_stamp"] = datetime.datetime.now().isoformat()
                        new_path = os.path.join("base_station", "sensor_data",
                                                f"{datetime.date.today().isoformat()}.csv")
                        if data_path != new_path:
                            # Switch data files
                            data_file.close()
                            data_path = new_path
                            data_file = open(data_path, "w", newline='')
                            need_header = True
                            data_writer = None
                        if data_writer is None:
                            data_writer = csv.DictWriter(data_file, fieldnames=flattened_data.keys())
                        if need_header:
                            data_writer.writeheader()
                            need_header = False
                        data_writer.writerow(flattened_data)
                        await self.broadcast_drivers(msg)
                    elif msg["type"] == "log":
                        # Route log to drivers
                        await self.log(f"Rover {sck.remote_address[0]} logged: {msg['message']}", msg["level"])
                    elif msg["type"] == "error":
                        await self.log(f"Rover {sck.remote_address[0]} reported error {msg['error']}: "
                                       f"{msg['message']}", "error")
                    else:
                        await sck.send(Msg.error(Error.invalid_message, "Unknown message type"))

                else:
                    await sck.close(1011, "Client was never registered")
        except Exception as e:
            # Send exception to drivers
            await self.log(str(e), "critical")
            raise e
        finally:
            data_file.close()
            await self.unregister_client(sck)
