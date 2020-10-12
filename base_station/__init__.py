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
from base_station.util import LOG_LEVELS, ClientsCollection


class RoverBaseStation:
    def __init__(self, _config: Config):
        self.config = _config

        # Clients collection
        self.clients = ClientsCollection()

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

    async def broadcast(self, message: str, role: str = None):
        """
        Send a message to multiple clients
        :param message: The message to send
        :param role: The role to send the message to, or None for all roles
        :return:
        """
        if role:
            role_clients = self.clients.with_role(role)
            if role_clients:
                await asyncio.wait([sck.send(message) for sck in role_clients])
        elif self.clients:
            await asyncio.wait([sck.send(message) for sck in self.clients])

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
        await self.broadcast(Msg.log(message, level), "driver")

    async def register_client(self, sck: websockets.WebSocketServerProtocol, path: str) -> bool:
        """
        Registers a new client connection
        :param sck: The client connection
        :param path: The connection path, used to determine whether the connected client is a Driver or a Rover.
        :return: Whether the client was successfully registered
        """
        # Determine role client is connecting as
        role_connect = self.config.auth.paths.get(path)
        if not role_connect:
            await self.log(f"Client tried to connect with invalid path: {sck.remote_address[0]}", "warning")
            await sck.send(Msg.error(Error.auth_error, "Invalid connection path"))
            await sck.close(1008, "Invalid path")
            return False
        # Authenticate client if enabled
        if self.config.auth.require_auth:
            groups = self.authenticate_client(sck)
            # Auth failed
            if groups is None:
                return False  # Close message and reason was already sent
            # Deny connect if user doesn't have perms to have role
            if role_connect not in groups:
                await self.log(f"Client tried to connect as role '{role_connect}' but does not "
                               f"have permission to: {sck.remote_address[0]}", "warning")
                await sck.send(Msg.error(Error.auth_error, "User does not have permission to have role"))
                await sck.close(1008, "Auth error")
                return False
        # If role is limited, deny if that role is "full"
        if self.config.auth.limits.get(role_connect) \
                and self.config.auth.limits[role_connect] > len(self.clients.with_role(role_connect)):
            await self.log(f"Client tried to connect as role '{role_connect}' but there "
                           f"are too many clients of that role connected", "warning")
            await sck.send(Msg.error(
                Error.too_many_clients, f"Too many clients are connected as role '{role_connect}'"))
            await sck.close(1008, f"Too many clients are connected as role")
            return False

        # Add client
        await self.log(f"Client connected: {role_connect}:{sck.remote_address[0]}")
        self.clients.add(sck, role_connect)
        return True

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
            await self.log(f"Received message with malformed JSON from {sck.remote_address[0]}", "error")
            await sck.send(Msg.error(Error.json_parse_error, "Failed to parse message"))
            await sck.close(1002, "Invalid JSON on auth message")
            return None
        # Error if invalid message format
        if not Msg.verify(auth_msg):
            await self.log(f"Received invalid message from {sck.remote_address[0]}", "error")
            await sck.send(Msg.error(Error.invalid_message, "The message sent is invalid"))
            await sck.close(1002, "Invalid auth message")
            return None
        # Error if first message is not of type `auth`
        if not auth_msg["type"] == "auth":
            await self.log(
                f"Expected `auth` message but received `{auth_msg['type']}` from {sck.remote_address[0]}",
                "error"
            )
            await sck.send(Msg.error(Error.auth_error, "Expected an auth message"))
            await sck.close(1008, "Expected an auth message on first message")
            return None
        # Check if user exists
        if not auth_msg["username"] in self.users:
            await self.log(
                f"Client tried to authenticate with nonexistent username '{auth_msg['username']}': "
                f"{sck.remote_address[0]}",
                "warning"
            )
            # Don't say "incorrect user" so attackers don't know if they have a valid username or not
            await sck.send(Msg.error(Error.auth_error, "Authentication failed"))
            await sck.close(1008, "Authentication failed")
            return None
        # Check password
        user = self.users[auth_msg["username"]]
        if not bcrypt.checkpw(auth_msg["password"].encode("utf-8"), user["pw_hash"].encode("ascii")):
            await self.log(f"Client tried to connect as user '{auth_msg['username']}' "
                           f"but failed to authenticate: {sck.remote_address[0]}", "warning")
            await sck.send(Msg.error(Error.auth_error, "Authentication failed"))
            await sck.close(1008, "Authentication failed")
            return None
        return user["groups"]

    async def unregister_client(self, sck: websockets.WebSocketServerProtocol):
        """
        Unregisters a client connection
        :param sck: The connection
        :return:
        """
        if sck in self.clients:
            await self.log(
                f"Client disconnected with code {sck.close_code}: {self.clients.get_role(sck)}:{sck.remote_address[0]}"
            )
            self.clients.remove(sck)
        else:
            await self.log(
                f"Client disconnected with code {sck.close_code} which was never registered: {sck.remote_address[0]}",
                "warning"
            )

    async def serve(self, sck: websockets.WebSocketServerProtocol, path: str):
        """
        Main entry point for WebSocket server.
        :param sck: The socket to serve for
        :param path: The path which the client connected to
        :return:
        """
        # Attempt to register client, exit if failed (connection is already closed)
        if not await self.register_client(sck, path):
            return

        try:
            # Continually receive messages
            async for msg_raw in sck:
                try:
                    # Decode and verify message formatting
                    try:
                        msg = json.loads(msg_raw)
                    except json.JSONDecodeError:
                        await self.log(f"Received message with malformed JSON from {sck.remote_address[0]}", "error")
                        await sck.send(Msg.error(Error.json_parse_error, "Failed to parse message"))
                        continue
                    if not Msg.verify(msg):
                        await self.log(f"Received invalid message from {sck.remote_address[0]}", "error")
                        await sck.send(Msg.error(Error.invalid_message, "The message sent is invalid"))
                        continue

                    await self.handlers[msg["type"]](self, sck, msg, self.clients.get_role(sck))

                # Catch all exceptions within loop so connection doesn't get closed
                except Exception as e:
                    # self.logger.exception(e)
                    # Send exception to drivers
                    await self.log(f"Base station error: {e!r}", "critical")

            # Connection closes with OK when look exits normally
            await self.unregister_client(sck)

        # Unregister clients when they disconnect
        except websockets.ConnectionClosed:
            await self.unregister_client(sck)

    # Message handlers
    async def _limit_role(self, sck: websockets.WebSocketServerProtocol, msg: dict, role: str, required_role: str):
        if role != required_role:
            await sck.send(Msg.error(Error.invalid_message, "Message type not allowed with role"))
            await self.log(
                f"Non-driver client {role}:{sck.remote_address[0]} sent message with type {msg['type']}",
                "warning"
            )
            return False
        return True

    async def _log(self, sck: websockets.WebSocketServerProtocol, msg: dict, role: str):
        await self.log(f"Client {role}:{sck.remote_address[0]} logged: {msg['message']}", msg["level"])

    async def _command(self, sck: websockets.WebSocketServerProtocol, msg: dict, role: str):
        if not await self._limit_role(sck, msg, role, "driver"):
            return
        # Store command id to route response later
        if msg["id"] in self.command_ids:
            await sck.send(Msg.error(Error.id_in_use, "The given command ID is already in use"))
            return
        self.command_ids[msg["id"]] = sck
        # Put the command in the command queue
        self.command_queue.append(msg)
        # Log command
        await self.log(
            f"{sck.remote_address} sent command {msg['command']} (#{msg['id']}) "
            f"with parameters {msg['parameters']} (#{len(self.command_queue)} in queue)"
        )

    async def _command_response(self, sck: websockets.WebSocketServerProtocol, msg: dict, role: str):
        if not await self._limit_role(sck, msg, role, "rover"):
            return
        # Route response to correct driver
        if msg["id"] not in self.command_ids:
            await sck.send(Msg.error(Error.unknown_id, "The given command ID is not valid"))
            await self.log(f"Command response received from rover {sck.remote_address[0]} "
                           f"with invalid id", "error")
            return
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

    async def _status(self, sck: websockets.WebSocketServerProtocol, msg: dict, role: str):
        if not await self._limit_role(sck, msg, role, "rover"):
            return
        status = msg["status"]
        if status == "busy":
            pass
        elif status == "idle":
            if not len(self.command_queue) == 0:
                next_command = self.command_queue.pop(0)
                await self.broadcast(json.dumps(next_command), "rover")
                await self.log(f"Sent command '{next_command['command']}' "
                               f"with parameters {next_command['parameters']!r}")
                self.current_command = next_command
        else:
            await self.log(f"Status message received from {sck.remote_address[0]} with an unknown "
                           f"status: {status}", "error")

    async def _clear_queue(self, sck: websockets.WebSocketServerProtocol, msg: dict, role: str):
        if not await self._limit_role(sck, msg, role, "driver"):
            return
        while len(self.command_queue) > 0:
            # Free up the ids of the removed commands
            cmd = self.command_queue.pop(0)
            del self.command_ids[cmd["id"]]
        await self.log(f"Queue cleared by {sck.remote_address[0]}")
        await self.broadcast(Msg.queue_status(self.current_command, self.command_queue), "driver")

    async def _option(self, sck: websockets.WebSocketServerProtocol, msg: dict, role: str):
        if not await self._limit_role(sck, msg, role, "driver"):
            return
        self.logger.info(f"{sck.remote_address[0]} getting options {msg['get']!r}, "
                         f"Setting options {msg['set']!r}")
        await self.broadcast(json.dumps(msg), "rover")

    async def _option_response(self, sck: websockets.WebSocketServerProtocol, msg: dict, role: str):
        if not await self._limit_role(sck, msg, role, "rover"):
            return
        await self.log(f"Option response from {sck.remote_address[0]}: {msg['values']!r}")
        await self.broadcast(json.dumps(msg), "driver")

    async def _sensors(self, sck: websockets.WebSocketServerProtocol, msg: dict, role: str):
        if not await self._limit_role(sck, msg, role, "rover"):
            return
        if self.config.data.enabled:
            points = [
                {
                    "measurement": meas,
                    "time": msg["time"],
                    "fields": fields
                } for meas, fields in msg["sensors"].values
            ]
            try:
                self.influx.write_points(points)
            except ConnectionError:
                await self.log(f"Unable to store sensor data submitted by {role}:{sck.remote_address[0]}", "error")
        await self.broadcast(json.dumps(msg), "driver")

    async def _query(self, sck: websockets.WebSocketServerProtocol, msg: dict, role: str):
        if not await self._limit_role(sck, msg, role, "driver"):
            return
        if msg["query"] == "client_list":
            await sck.send(Msg.query_response("client_list", {
                "drivers": [s.remote_address[0] for s in self.clients.with_role("driver")],
                "rovers": [s.remote_address[0] for s in self.clients.with_role("rover")]
            }))
        else:
            await sck.send(Msg.error(Error.invalid_message, "Invalid query type"))
            await self.log(f'Received and invalid query from {sck.remote_address}')

    async def _error(self, sck: websockets.WebSocketServerProtocol, msg: dict, role: str):
        if not await self._limit_role(sck, msg, role, "driver"):
            return
        await self.log(f"Client {role}:{sck.remote_address[0]} reported error {msg['error']}: "
                       f"{msg['message']}", "error")

    async def _e_stop(self, sck: websockets.WebSocketServerProtocol, msg: dict, role: str):
        await self.broadcast(json.dumps(msg), "rover")
        await self.log(f"Client {role}:{sck.remote_address[0]} activated e-stop!", "warning")

    async def _auth(self, sck: websockets.WebSocketServerProtocol, _msg: dict, role: str):
        # Either already authenticated or authentication is not required
        if self.config.auth.require_auth:
            await self.log(f"Client tried to authenticate while already authenticated: {role}:{sck.remote_address[0]}",
                           "warning")
            await sck.send(Msg.error(
                Error.auth_error,
                "Attempted to authenticate while already authenticated"
            ))
        # Ignore auth message if not required

    handlers: t.Dict[str, t.Callable[[t.Any, websockets.WebSocketServerProtocol, dict, str], t.Awaitable[None]]] = {
        "log": _log,
        "command": _command,
        "command_response": _command_response,
        "status": _status,
        "clear_queue": _clear_queue,
        "option": _option,
        "option_response": _option_response,
        "sensors": _sensors,
        "query": _query,
        "error": _error,
        "e_stop": _e_stop,
        "auth": _auth
    }
