import asyncio
import json
import websockets
import typing as t
import logging, logging.handlers
import datetime
import os
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


class RoverBaseStation:
    def __init__(self):
        self.drivers: t.Set[websockets.WebSocketServerProtocol] = set()
        self.rovers: t.Set[websockets.WebSocketServerProtocol] = set()

        self.command_ids: t.Dict[int, websockets.WebSocketServerProtocol] = {}
        self.command_queue: asyncio.Queue

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
        await asyncio.wait([sck.send(message) for sck in self.drivers.union(self.rovers)])

    async def broadcast_drivers(self, message: str):
        """
        Broadcasts a message to all Drivers
        :param message: The message to send
        :return:
        """
        await asyncio.wait([sck.send(message) for sck in self.drivers])

    async def broadcast_rovers(self, message: str):
        """
        Broadcasts a message to all Rovers
        :param message: The message to send
        :return:
        """
        await asyncio.wait([sck.send(message) for sck in self.rovers])

    async def log(self, message: str, level="info"):
        """
        Broadcasts a log message to the connected Drivers
        :param message: The message to send
        :param level: The loglevel or "severity" to indicate (debug, info, warning, error, critical)
        :return:
        """
        if level.lower() in LOG_LEVELS:
            self.logger.log(LOG_LEVELS[level], message)
        else:
            self.logger.warning("Invalid logging level: " + level)
            self.logger.warning(message)
        await self.broadcast_drivers(Msg.log(message, level))

    async def register_client(self, sck: websockets.WebSocketServerProtocol, path: str):
        """
        Registers a new client connection
        :param sck: The client connection
        :param path: The connection path, used to determine whether the connected client is a Driver or a Rover.
        :return:
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
            await sck.close(1008, "Invalid path")
            return

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
        await self.register_client(sck, path)

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
                        # Forward command to rover
                        await self.broadcast_rovers(json.dumps(msg))
                        # Log command
                        await self.log(
                            f"{sck.remote_address[0]} sent command {msg['command']} (#{msg['id']}) "
                            f"with parameters {msg['parameters']}"
                        )
                    elif msg["type"] == "option":
                        pass
                    elif msg["type"] == "log":
                        # Route log to drivers
                        await self.log(f"Driver {sck.remote_address[0]} logged: {msg['message']}", msg["level"])

                elif sck in self.rovers:
                    if msg["type"] == "command_response":
                        # Route response to correct driver
                        if msg["id"] not in self.command_ids:
                            await sck.send(Msg.error(Error.unknown_id, "The given command ID is not valid"))
                            continue
                        await self.command_ids[msg["id"]].send(json.dumps(msg))
                        # Log (debug)
                        await self.log(
                            f"{sck.remote_address[0]} sent response (#{msg['id']}) to "
                            f"{self.command_ids[msg['id']].remote_address[0]}"
                        )
                        # Free up command id
                        # May cause issues if more than 1 rover is connected, which shouldn't ever be the case
                        del self.command_ids[msg["id"]]
                    elif msg["type"] == "log":
                        # Route log to drivers
                        await self.log(f"Rover {sck.remote_address[0]} logged: {msg['message']}", msg["level"])

                else:
                    await sck.close(1011, "Client was never registered")

        finally:
            await self.unregister_client(sck)
