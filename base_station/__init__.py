import asyncio
import csv
import json
import os
import websockets
import typing as t
import logging
import datetime
from common import Msg, Error


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

        self.logger: logging.Logger = logging.getLogger("base_station")
        self.log_path: str = "logs/" + datetime.date.today().isoformat() + ".log"
        logging.basicConfig(filename=self.log_path, level=logging.DEBUG,
                            format='%(asctime)s [%(levelname)s] [%(name)s: %(module)s.%(funcName)s] %(message)s')

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
        Broadcasts a log message to the connected Drivers and writes to local log
        :param message: The message to send
        :param level: The loglevel to indicate (debug, info, warning, error, critical)
        :return:
        """

        new_log_file = "logs/" + datetime.date.today().isoformat() + ".log"
        if self.log_path != new_log_file:
            self.log_path = new_log_file
            logging.basicConfig(filename=new_log_file)

        if level == "debug":
            self.logger.debug(message)
        elif level == "info":
            self.logger.info(message)
        elif level == "warning":
            self.logger.warning(message)
        elif level == "error":
            self.logger.error(message)
        elif level == "critical":
            self.logger.critical(message)
        else:
            self.logger.warning(f"Invalid logging level: {level}")
            self.logger.warning(message)
        await self.broadcast_drivers(Msg.log(message, level))

    async def register_client(self, sck: websockets.WebSocketServerProtocol, path: str):
        """
        Registers a new client connection
        :param sck: The client connection
        :param path: The connection path, used to determine whether the connected client is a Driver or a Rover.
        :return:
        """
        print(path)
        if "driver" in path:
            self.drivers.add(sck)
            await self.log(f"New driver connected: {sck.remote_address}")
        elif "rover" in path:
            self.rovers.add(sck)
            if len(self.rovers) > 1:
                await self.log(f"Rover connected while one was already connected: {sck.remote_address}", "warning")
            else:
                await self.log(f"Rover connected: {sck.remote_address}")
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
            await self.log(f"Driver disconnected: {sck.remote_address}")
        elif sck in self.rovers:
            self.drivers.remove(sck)
            await self.log(f"Rover disconnected: {sck.remote_address}")
        else:
            await self.log(f"Client disconnected which was never registered: {sck.remote_address}", "warning")

    async def serve(self, sck: websockets.WebSocketServerProtocol, path: str):
        await self.register_client(sck, path)

        data_path: str = os.path.join("base_station", "sensor_data", f"{datetime.date.today().isoformat()}.csv")
        need_header: bool = not os.path.exists(data_path)
        data_file: t.TextIO = open(data_path, "a", newline='')
        data_writer: t.Optional[csv.DictWriter] = None
        try:
            async for msg_raw in sck:  # Continually receive messages
                try:
                    msg = json.loads(msg_raw)
                    if not Msg.verify(msg):
                        await sck.send(Msg.error(Error.invalid_message, "The message sent is invalid"))
                        await self.log(f"Received invalid message from {sck.remote_address}", "error")

                    if sck in self.drivers:
                        if msg["type"] == "command":
                            # Store command id to route response later
                            if msg["id"] in self.command_ids:
                                await sck.send(Msg.error(Error.id_in_use, "The given command ID is already in use"))
                                continue
                            self.command_ids[msg["id"]] = sck
                            # Put the command in the command queue
                            await self.command_queue.append(msg)
                            # Log command
                            await self.log(
                                f"{sck.remote_address} sent command {msg['command']} (#{msg['id']}) "
                                f"with parameters {msg['parameters']}"
                            )
                        elif msg["type"] == "clear_queue":
                            while len(self.command_queue) > 0:
                                # Free up the ids of the removed commands
                                cmd = self.command_queue.pop(0)
                                del self.command_ids[cmd["id"]]
                            await self.log("Queue cleared")
                            await self.broadcast_drivers(Msg.queue_status(self.current_command, self.command_queue))
                        elif msg["type"] == "option":
                            self.logger.info(f"Getting options {msg['get']!r}, Setting options {msg['set']!r}")
                            await self.broadcast_rovers(msg)
                        else:
                            self.logger.error(f"Received message with an unknown type from {sck.remote_address}")
                            await sck.send(Msg.error(Error.invalid_message, "Unknown message type"))

                    elif sck in self.rovers:
                        if msg["type"] == "log":
                            await self.log("Rover: " + msg["message"], msg["level"])
                        elif msg["type"] == "command_response":
                            # Route response to correct driver
                            if msg["id"] not in self.command_ids:
                                await self.log("Command received from rover with invalid id", "error")
                                await sck.send(Msg.error(Error.unknown_id, "The given command ID is not valid"))
                                continue
                            await self.command_ids[msg["id"]].send(json.dumps(msg))
                            # Log (debug)
                            await self.log(
                                f"{sck.remote_address} sent response (#{msg['id']}) to "
                                f"{self.command_ids[msg['id']].remote_address}"
                            )
                            # Free up command id
                            # May cause issues if more than 1 rover is connected, which shouldn't ever be the case
                            if self.current_command is None or msg["id"] != self.current_command["id"]:
                                await self.log("Command response received that does not match the running command",
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
                                await self.log(f"Status message received with an unknown status: {status}", "error")
                        elif msg["type"] == "option_response":
                            await self.log(f"Option response: {msg['values']!r}")
                            await self.broadcast_drivers(msg)
                        elif msg["type"] == "digest":
                            flattened_data = flatten_dict(msg)
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
                        else:
                            await sck.send(Msg.error(Error.invalid_message, "Unknown message type"))

                    else:
                        await sck.close(1011, "Client was never registered")

                except json.JSONDecodeError:
                    await sck.send(Msg.error(Error.json_parse_error, "Failed to parse the message"))
                    await self.log(f"Received message with malformed JSON from {sck.remote_address}", "error")
        except Exception as e:
            await self.log(str(e), "critical")
            raise e
        finally:
            data_file.close()
            await self.unregister_client(sck)
