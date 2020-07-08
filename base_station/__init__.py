import asyncio
import json
import websockets
import typing as t
from common import Msg


class RoverBaseStation:
    def __init__(self):
        self.drivers: t.Set[websockets.WebSocketServerProtocol] = set()
        self.rovers: t.Set[websockets.WebSocketServerProtocol] = set()

        self.command_ids: t.Dict[int, websockets.WebSocketServerProtocol] = {}
        self.command_queue: asyncio.Queue

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
        :param level: The loglevel to indicate (debug, info, warning, error, critical)
        :return:
        """
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

        try:
            async for msg_raw in sck:  # Continually receive messages
                try:
                    msg = json.loads(msg_raw)
                    if not Msg.verify(msg):
                        await sck.send(Msg.error("invalid_message", "The message sent is invalid"))
                        await self.log(f"Received invalid message from {sck.remote_address}", "error")

                    if sck in self.drivers:
                        if msg["type"] == "command":
                            # Store command id to route response later
                            if msg["id"] in self.command_ids:
                                await sck.send(Msg.error("id_in_use", "The given command ID is already in use"))
                                continue
                            self.command_ids[msg["id"]] = sck
                            # Forward command to rover
                            await self.broadcast_rovers(json.dumps(msg))
                            # Log command
                            await self.log(
                                f"{sck.remote_address} sent command {msg['command']} (#{msg['id']}) "
                                f"with parameters {msg['parameters']}"
                            )
                        if msg["type"] == "option":
                            pass

                    elif sck in self.rovers:
                        if msg["type"] == "response":
                            # Route response to correct driver
                            if msg["id"] not in self.command_ids:
                                await sck.send(Msg.error("unknown_id", "The given response ID is not valid"))
                                continue
                            await self.command_ids[msg["id"]].send(json.dumps(msg))
                            # Log (debug)
                            await self.log(
                                f"{sck.remote_address} sent response (#{msg['id']}) to "
                                f"{self.command_ids[msg['id']].remote_address}"
                            )
                            # Free up command id
                            # May cause issues if more than 1 rover is connected, which shouldn't ever be the case
                            del self.command_ids[msg["id"]]

                    else:
                        await sck.close(1011, "Client was never registered")

                except json.JSONDecodeError:
                    await sck.close(1002, "Message frame contained malformed JSON")
                    await self.log(f"Received message with malformed JSON from {sck.remote_address}", "error")

        finally:
            await self.unregister_client(sck)
