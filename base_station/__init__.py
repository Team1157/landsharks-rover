import asyncio
import json
import websockets
import typing as t
import logging
import logging.handlers
import bcrypt
import influxdb
from common import Msg, Error
from base_station.config import Config
from base_station.util import LOG_LEVELS, flatten_dict


class RoverBaseStation:
    def __init__(self, _config: Config):
        self.config = _config

        # Rovers and drivers collections
        self.drivers: t.Set[websockets.WebSocketServerProtocol] = set()
        self.rovers: t.Set[websockets.WebSocketServerProtocol] = set()

        # Command queue
        self.command_ids: t.Dict[int, websockets.WebSocketServerProtocol] = {}
        self.command_queue: t.List[t.Dict[str, t.Any]] = []
        self.current_command: t.Optional[t.Dict[str, t.Any]] = None

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
        # File hanlder
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
        # Authenticate client if enabled
        if self.config.auth.require_auth:
            auth = self.authenticate_client(sck)
            if not auth:
                return False
            # TODO: check user groups
        # Determine access mode
        if path == "/driver":
            if self.config.auth.limit_drivers and len(self.drivers) < self.config.auth.limit_drivers:
                self.drivers.add(sck)
                await self.log(f"New driver connected: {sck.remote_address[0]}")
            else:
                await self.log(f"Driver tried to connect but too many drivers are connected: {sck.remote_address[0]}")
                await sck.close(1008, "Too many drivers are connected")
        elif path == "/rover":
            if self.config.auth.limit_rovers and len(self.rovers) < self.config.auth.limit_rovers:
                self.rovers.add(sck)
                if len(self.rovers) > 1:
                    await self.log(
                        f"Rover connected while one was already connected: {sck.remote_address[0]}",
                        "warning"
                    )
                else:
                    await self.log(f"Rover connected: {sck.remote_address[0]}")
            else:
                await self.log(f"Rover tried to connect but too many rovers are connected: {sck.remote_address[0]}")
                await sck.close(1008, "Too many rovers are connected")
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

    async def authenticate_client(self, sck: websockets.WebSocketServerProtocol):
        """
        Authenticates a client connection
        :param sck:
        :return: the list of groups which the client belongs to, or None if the authentication failed
        """
        # Receive first message, which should be an `auth` message
        auth_msg_raw = await sck.recv()
        try:
            auth_msg = json.loads(auth_msg_raw)
        # Error if invalid JSON
        except json.JSONDecodeError:
            await sck.send(Msg.error(Error.json_parse_error, "Failed to parse message"))
            await self.log(f"Received message with malformed JSON from {sck.remote_address[0]}", "error")
            return False
        # Error if invalid message format
        if not Msg.verify(auth_msg):
            await sck.send(Msg.error(Error.invalid_message, "The message sent is invalid"))
            await self.log(f"Received invalid message from {sck.remote_address[0]}", "error")
            return False
        # Error if first message is not of type `auth`
        if not auth_msg["type"] == "auth":
            await sck.send(Msg.error(Error.auth_error, "Expected an `auth` message"))
            await self.log(
                f"Expected `auth` message but received `{auth_msg['type']}` from {sck.remote_address[0]}",
                "error"
            )
            return False
        # Check if user exists
        if not auth_msg["username"] in self.users:
            await sck.send(Msg.error(Error.auth_error, "Authentication failed"))
            await self.log(
                f"Client tried to authenticate with nonexistent username {auth_msg['username']}: "
                f"{sck.remote_address[0]}",
                "warning"
            )
            return False
        # Check password
        user = self.users[auth_msg["username"]]
        if not bcrypt.checkpw(auth_msg["password"].encode("utf-8"), user["pw_hash"].encode("ascii")):
            await sck.send(Msg.error(Error.auth_error, "Authentication failed"))
            await self.log(f"Client tried to connect but failed to authenticate: {sck.remote_address[0]}", "warning")
            return False
        return user["groups"]

    async def serve(self, sck: websockets.WebSocketServerProtocol, path: str):
        """
        Main entry point for WebSocket server.
        :param sck: The socket to serve for
        :param path: The path which the client connected to
        :return:
        """
        # Attempt to register cleint, and close connection if failed
        if not await self.register_client(sck, path):
            return

        try:
            # Continually receive messages
            async for msg_raw in sck:
                # Decode and verify message formatting
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
                    if msg["type"] == "auth":
                        # Either already authenticated or authentication is not required
                        if self.config.auth.require_auth:
                            await sck.send(Msg.error(
                                Error.auth_error,
                                "Attempted to authenticate while already authenticated"
                            ))
                        # Ignore auth message if not required
                    elif msg["type"] == "command":
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
                    elif msg["type"] == "query":
                        if msg["query"] == "client_list":
                            await sck.send(Msg.query_response(
                                "client_list",
                                {
                                    "drivers": [s.remote_address[0] for s in self.drivers],
                                    "rovers": [s.remote_address[0] for s in self.rovers]
                                }))
                        else:
                            await sck.send(Msg.error(Error.invalid_message, "Invalid query type"))
                            await self.log(f'Received and invalid query from {sck.remote_address}')
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
                    elif msg["type"] == "sensors":
                        if self.config.data.enabled:
                            points = [
                                {
                                    "measurement": meas,
                                    "time": msg["time"],
                                    "fields": fields
                                } for meas, fields in msg["sensors"].values
                            ]
                            self.influx.write_points(points)
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
            self.logger.exception(e)
            # Send exception to drivers
            await self.log("Base station error: " + repr(e), "critical")
        finally:
            await self.unregister_client(sck)
