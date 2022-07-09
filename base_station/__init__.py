import asyncio
import json

import serde
import websockets
import typing as t
import logging
import logging.handlers
import bcrypt
import influxdb
from common import *
from base_station.config import Config
from base_station.util import LOG_LEVELS, Client


class RoverBaseStation:
    def __init__(self, _config: Config):
        self.config = _config

        # Clients collection
        self.clients: t.Set[Client] = set()

        # #  LOGGING CONFIGURATION  # #
        # Create formatter
        fmt = logging.Formatter(self.config.logging.format, style=self.config.logging.format_style)
        # Handlers
        handlers = []
        # Stream handler
        if self.config.logging.handlers.stream.enabled:
            stream_handl = logging.StreamHandler(self.config.logging.handlers.stream.stream)
            stream_handl.setFormatter(fmt)
            stream_handl.setLevel(self.config.logging.handlers.stream.level)
            handlers.append(stream_handl)
        # File handler
        if self.config.logging.handlers.file.enabled:
            if self.config.logging.handlers.file.rotate:
                file_handl = logging.handlers.TimedRotatingFileHandler(
                    self.config.logging.handlers.file.path,
                    when=self.config.logging.handlers.file.rotate_when,
                    interval=self.config.logging.handlers.file.rotate_interval
                )
            else:
                file_handl = logging.FileHandler(self.config.logging.handlers.file.path)
            file_handl.setFormatter(fmt)
            file_handl.setLevel(self.config.logging.handlers.file.level)
            handlers.append(file_handl)
        # Create main logger and add handlers
        self.logger = logging.getLogger(self.config.logging.main_logger.name)
        self.logger.setLevel(self.config.logging.main_logger.level)
        for handler in handlers:
            self.logger.addHandler(handler)
        # Get extra loggers an add handlers
        for logger, level in self.config.logging.extra_loggers.items():
            log = logging.getLogger(logger)
            log.setLevel(level)
            for handler in handlers:
                log.addHandler(handler)

        # Load user authentication "database"
        if self.config.auth.require_auth:
            try:
                with open("rover_users.json", "r") as f:
                    self.users = json.load(f)
            except FileNotFoundError:
                self.logger.critical("Unable to open rover_users.json: file does not exist.")
                raise SystemExit(1)

        # Connect to InfluxDB
        if self.config.data.enabled:
            self.influx = influxdb.InfluxDBClient(
                host=self.config.data.influx_host,
                port=self.config.data.influx_port,
                username=self.config.data.influx_user,
                password=self.config.data.influx_pass,
                database=self.config.data.influx_db
            )

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
        await self.log(f"Client {sck.remote_address[0]} connected as user {username} ({role})")
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
            await sck.send_msg(LogMessage(message="Invalid auth message", level="error"))
            await sck.close(1002, "Invalid auth message")
            return None
        # Error if first message is not of type `auth`
        if not isinstance(auth_msg, AuthMessage):
            await self.log(f"Expected auth message but received `{auth_msg.tag_name}` from {sck.remote_address[0]}",
                           "error")
            await sck.send_msg(LogMessage(message="Expected an auth message", level="error"))
            await sck.close(1008, "Expected an auth message on first message")
            return None
        # Check if user exists
        # TODO redo user system
        if not auth_msg["username"] in self.users:
            await self.log(f"Client tried to authenticate with nonexistent username "
                           f"'{auth_msg['username']}': {sck.remote_address[0]}", "warning")
            # Don't say "incorrect user" so attackers don't know if they have a valid username or not
            await sck.send_msg(LogMessage(message="Authentication failed", level="error"))
            await sck.close(1008, "Authentication failed")
            return None
        # Check password
        user = self.users[auth_msg["username"]]
        if not bcrypt.checkpw(auth_msg["password"].encode("utf-8"), user["pw_hash"].encode("ascii")):
            await self.log(f"Client tried to connect as user '{auth_msg['username']}' "
                           f"but failed to authenticate: {sck.remote_address[0]}", "warning")
            await sck.send_msg(LogMessage(message="Authentication failed", level="error"))
            await sck.close(1008, "Authentication failed")
            return None
        return "todo"

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
                    await self.handlers[msg.__class__](self, client, msg)

                except (serde.ValidationError, json.JSONDecodeError):
                    await self.log(f"Received invalid message from {client.ip}", "error")
                    # await sck.send_msg(LogMessage(message="Invalid message", level="error"))
                    continue

                # Catch all exceptions within loop so connection doesn't get closed
                except Exception as e:
                    # self.logger.exception(e)
                    # Send exception to drivers
                    await self.log(f"Base station error: {e!r}", "error")

        # Unregister clients when the connection loop ends even if it errors
        finally:
            await self.unregister_client(client)

    # #  MESSAGE HANDLERS  # #

    handlers = {}

    # Registers a message handler
    @classmethod
    def handler(cls, message_type: t.Type, sender: t.Optional[Role] = None):
        def decorate(fn: t.Callable[[RoverBaseStation, Client, Message], None]):
            if sender is not None:
                def wrapper(self: RoverBaseStation, client: Client, msg: Message):
                    if client.role != sender:
                        await self.log(f"User {client.username} ({client.role.name}) sent"
                                       f" unexpected {msg.tag_name} message", "error")
                        return
                    fn(self, client, msg)
                cls.handlers[message_type] = wrapper

            else:
                cls.handlers[message_type] = fn

        return decorate

    @handler(LogMessage)
    async def handle_log(self, client: Client, msg: LogMessage):
        await self.log(f"User {client.username} ({client.role.name}) logged: {msg.message}", msg.level)

    @handler(CommandMessage, Role.DRIVER)
    async def handle_command(self, client: Client, msg: CommandMessage):
        # Forward command to rover
        await self.broadcast(msg, Role.ROVER)
        # Log command
        await self.log(f"Driver {client.username} sent command {msg.command.tag_name}")

    @handler(CommandEndedMessage, Role.ROVER)
    async def handle_command_ended(self, client: Client, msg: CommandEndedMessage):
        # Forward to drivers
        await self.broadcast(msg, Role.DRIVER)
        # Log ending
        await self.log(f"Rover {client.username} completed command {msg.command.tag_name}: {msg.completed}")

    @handler(CommandStatusMessage, Role.ROVER)
    async def handle_command_status(self, _client: Client, msg: CommandStatusMessage):
        # Forward to drivers
        await self.broadcast(msg, Role.DRIVER)

    @handler(OptionMessage, Role.DRIVER)
    async def handle_option(self, client: Client, msg: OptionMessage):  # TODO
        self.logger.info(f"{client.ip} getting options {msg.get!r}, "
                         f"Setting options {msg.set!r}")
        await self.broadcast(msg, Role.ROVER)

    @handler(OptionResponseMessage)
    async def handle_option_response(self, client: Client, msg: OptionResponseMessage):  # TODO
        # Message should not be received by the base station
        pass

    @handler(SensorDataMessage, Role.ROVER)
    async def handle_sensor_data(self, _client: Client, msg: OptionResponseMessage):
        # Forward to drivers
        await self.broadcast(msg, Role.DRIVER)
        # TODO log sensor data

    @handler(QueryBaseMessage, Role.DRIVER)
    async def handle_query_base(self, client: Client, msg: QueryBaseMessage):  # TODO
        pass

    @handler(QueryBaseResponseMessage)
    async def handle_query_base_response(self, client: Client, msg: QueryBaseResponseMessage):  # TODO
        # Message should not be received by the base station
        pass

    @handler(EStopMessage)
    async def _e_stop(self, client: Client, msg: EStopMessage):
        await self.broadcast(msg, Role.ROVER)
        await self.log(f"Client {client.username} ({client.role.name}) activated e-stop!", "warning")

    @handler(AuthMessage)
    async def _auth(self, sck: websockets.WebSocketServerProtocol, _msg: dict, role: str):  # TODO
        # Message should not be received after the auth step
        pass
