import asyncio
import json
import os
import pathlib
import sqlite3
import traceback

import serde
import toml
import websockets
import typing as t
import logging
import logging.handlers
from common import *
from base_station.config import Config
from base_station.util import LOG_LEVELS, Client


class RoverBaseStation:
    def __init__(self):
        module_path = pathlib.Path(os.path.dirname(__file__))

        with open(module_path / "config.toml") as f:
            self.config = Config(toml.load(f))

        # Clients collection
        self.clients: t.Set[Client] = set()

        # #  LOGGING CONFIGURATION  # #
        # Create formatter
        fmt = logging.Formatter(
            "{asctime} [{levelname}] [{name}: {module}.{funcName}] {message}",
            style="{"
        )
        # Handlers
        # Stream handler
        stream_handl = logging.StreamHandler()
        stream_handl.setFormatter(fmt)
        stream_handl.setLevel(logging.INFO)
        # File handler
        file_handl = logging.handlers.TimedRotatingFileHandler(
            module_path / "logs" / "base_station.log",
            when="midnight",
            interval=1
        )
        file_handl.setFormatter(fmt)
        file_handl.setLevel(logging.DEBUG)

        handlers = [stream_handl, file_handl]
        # Logger setup
        for logger, level in {
            "sandshark": logging.DEBUG,
            "websockets": logging.INFO,
            "websockets.protocol": logging.INFO,
            "websockets.server": logging.INFO
        }.items():
            logger = logging.getLogger(logger)
            logger.setLevel(level)
            for handler in handlers:
                logger.addHandler(handler)

        # Main logger
        self.logger = logging.getLogger("sandshark")

        # Connect to sensor data database and initialize
        self.db = sqlite3.connect(module_path / "sensor_data" / "data.db")
        cur = self.db.cursor()
        cur.execute("""
            create table if not exists sensors (
                id integer primary key autoincrement,
                time text,
                sensor text,
                measurement text,
                value float
            )
        """)
        self.db.commit()

        # Load user authentication "database"
        try:
            with open(module_path / "rover_users.json", "r") as f:
                self.userbase = json.load(f)
        except FileNotFoundError:
            self.logger.critical("Unable to open rover_users.json: file does not exist.")
            raise SystemExit(1)

        self.logger.info("Rover base station starting!")

    async def broadcast(self, message: Message, role: t.Optional[Role] = None):
        """
        Send a message to multiple clients
        :param message: The message to send
        :param role: The role to send the message to, or None for all roles
        :return:
        """
        if role:
            role_clients = {client for client in self.clients if client.role == role}
            if role_clients:
                await asyncio.wait([client.sck.send_msg(message) for client in role_clients])
        elif self.clients:
            await asyncio.wait([client.sck.send_msg(message) for client in self.clients])

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
        await self.broadcast(LogMessage(message=message, level=level), Role.DRIVER)

    async def register_client(self, sck: websockets.WebSocketServerProtocol, path: str) -> t.Optional[Client]:
        """
        Registers a new client connection
        :param sck: The client connection
        :param path: The connection path, used to determine whether the connected client is a Driver or a Rover.
        :return: The client object created in registration
        """
        # Determine role client is connecting as
        role = Role.from_path(path)
        if not role:
            await self.log(f"Client {sck.remote_address[0]} tried to connect with invalid path: {path}", "warning")
            await sck.send_msg(LogMessage(message="Invalid path", level="error"))
            await sck.close(1008, "Invalid path")
            return None

        # Authenticate client
        username = await self.authenticate_client(sck)
        if username is None:
            return None  # Close message and reason was already sent

        # Add client
        await self.log(f"Client {sck.remote_address[0]} connected as user {username} ({role.name})")
        client = Client(sck, username, role)
        self.clients.add(client)
        return client

    async def authenticate_client(self, sck: websockets.WebSocketServerProtocol) -> t.Optional[str]:
        """
        Authenticates a client connection
        :param sck: the socket to authenticate
        :return: the username authenticated, or None if the authentication failed
        """
        # Receive first message, which should be an `auth` message
        auth_msg_raw = await sck.recv()
        try:
            auth_msg = Message.from_json(auth_msg_raw)
        # Error if invalid message
        except (serde.ValidationError, json.JSONDecodeError):
            await self.log(f"Received invalid auth message from {sck.remote_address[0]}", "error")
            await sck.send_msg(AuthResponseMessage(success=False))
            await sck.send_msg(LogMessage(message="Invalid auth message", level="error"))
            await sck.close(1002, "Invalid auth message")
            return None
        # Error if first message is not of type `auth`
        if not isinstance(auth_msg, AuthMessage):
            await self.log(f"Expected auth message but received `{auth_msg.tag_name}` from {sck.remote_address[0]}",
                           "error")
            await sck.send_msg(AuthResponseMessage(success=False))
            await sck.send_msg(LogMessage(message="Expected an auth message", level="error"))
            await sck.close(1008, "Expected an auth message on first message")
            return None

        # Check token
        user = self.userbase.get(auth_msg.token)
        if not user:
            await self.log(f"Client {sck.remote_address[0]} tried to authenticate with unknown token", "warning")
            await sck.send_msg(AuthResponseMessage(success=False))
            await sck.send_msg(LogMessage(message="Authentication failed", level="error"))
            await sck.close(1008, "Authentication failed")
            return None

        await sck.send_msg(AuthResponseMessage(success=True, user=user))
        return user

    async def unregister_client(self, client: Client):
        """
        Unregisters a client connection
        :param client: The client
        """
        if client in self.clients:
            await self.log(f"User {client.username} ({client.role}) disconnected with code {client.sck.close_code}",
                           "info" if client.sck.close_code <= 1001 else "warning")
            self.clients.remove(client)
        else:
            await self.log(f"User {client.username} ({client.role}) disconnected with code {client.sck.close_code} "
                           f"but was never registered", "warning")

    async def serve(self, sck: websockets.WebSocketServerProtocol, path: str):
        """
        Main entry point for WebSocket server.
        :param sck: The socket to serve for
        :param path: The path which the client connected to
        """
        # Attempt to register client, exit if failed (connection is already closed)
        client = await self.register_client(sck, path)
        if not client:
            return

        try:
            # Continually receive messages
            async for msg_raw in client.sck:  # raises websockets.ConnectionClosed on close
                try:
                    # Decode and verify message formatting
                    msg = Message.from_json(msg_raw)
                    # Delegate to message handler
                    await message_handlers.get(msg.__class__, default_handler)(self, client, msg)

                except (serde.ValidationError, json.JSONDecodeError):
                    await self.log(f"Received invalid message from {client.ip}", "error")
                    # await sck.send_msg(LogMessage(message="Invalid message", level="error"))
                    continue

                # Catch all exceptions within loop so connection doesn't get closed
                except Exception as e:
                    # self.logger.exception(e)
                    # Send exception to drivers
                    await self.log(f"Base station error: {traceback.format_exc()}", "error")

        except websockets.ConnectionClosed:
            pass

        # Unregister clients when the connection loop ends even if it errors
        finally:
            await self.unregister_client(client)

    async def main(self, *args, **kwargs):
        async with websockets.serve(self.serve, *args, **kwargs):
            await asyncio.Future()  # run forever


# #  MESSAGE HANDLERS  # #
message_handlers = {}


# Registers a message handler
def message_handler(message_type: t.Type, sender: t.Optional[Role] = None):
    def decorate(fn: t.Callable[[RoverBaseStation, Client, Message], t.Coroutine]):
        if sender is not None:
            async def wrapper(self: RoverBaseStation, client: Client, msg: Message):
                if client.role != sender:
                    await self.log(f"User {client.username} ({client.role.name}) sent"
                                   f" unexpected {msg.tag_name} message", "error")
                    return
                await fn(self, client, msg)

            message_handlers[message_type] = wrapper

        else:
            message_handlers[message_type] = fn

    return decorate


@message_handler(LogMessage)
async def handle_log(self: RoverBaseStation, client: Client, msg: LogMessage):
    # Format log and forward
    await self.log(f"User {client.username} ({client.role.name}) logged: {msg.message}", msg.level)


@message_handler(CommandMessage, Role.DRIVER)
async def handle_command(self: RoverBaseStation, client: Client, msg: CommandMessage):
    # Forward command to rover
    await self.broadcast(msg, Role.ROVER)
    # Log command
    if msg.command is None:
        await self.log(f"Driver {client.username} cancelled the current command")
    else:
        await self.log(f"Driver {client.username} sent command {msg.command.tag_name}")


@message_handler(CommandEndedMessage, Role.ROVER)
async def handle_command_ended(self: RoverBaseStation, client: Client, msg: CommandEndedMessage):
    # Forward to drivers
    await self.broadcast(msg, Role.DRIVER)
    # Log ending
    await self.log(f"Rover {client.username} completed command {msg.command.tag_name}: {msg.completed}")


@message_handler(CommandStatusMessage, Role.ROVER)
async def handle_command_status(self: RoverBaseStation, _client: Client, msg: CommandStatusMessage):
    # Forward to drivers
    await self.broadcast(msg, Role.DRIVER)


@message_handler(OptionMessage, Role.DRIVER)
async def handle_option(self: RoverBaseStation, _client: Client, msg: OptionMessage):
    # Forward to rover
    await self.broadcast(msg, Role.ROVER)


@message_handler(OptionResponseMessage, Role.ROVER)
async def handle_option_response(self: RoverBaseStation, _client: Client, msg: OptionResponseMessage):
    # Forward to drivers
    await self.broadcast(msg, Role.DRIVER)


@message_handler(SensorDataMessage, Role.ROVER)
async def handle_sensor_data(self: RoverBaseStation, _client: Client, msg: SensorDataMessage):
    # Forward to drivers
    await self.broadcast(msg, Role.DRIVER)
    cur = self.db.cursor()
    for measurement, value in msg.measurements.items():
        cur.execute("""
            insert into sensors (time, sensor, measurement, value)
            values (?, ?, ?, ?)
        """, (msg.time, msg.sensor, measurement, value))
    self.db.commit()


@message_handler(QueryBaseMessage, Role.DRIVER)
async def handle_query_base(_self: RoverBaseStation, _client: Client, _msg: QueryBaseMessage):  # TODO
    pass


@message_handler(EStopMessage)
async def handle_e_stop(self: RoverBaseStation, client: Client, msg: EStopMessage):
    await self.broadcast(msg, Role.ROVER)
    await self.log(f"Client {client.username} ({client.role.name}) activated e-stop!", "warning")


async def default_handler(self: RoverBaseStation, client: Client, msg: Message):
    await self.log(f"Received unexpected {msg.tag_name} message from {client.username} ({client.role.name})", "warning")
