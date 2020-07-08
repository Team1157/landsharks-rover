import asyncio
import json
import typing as t
import inspect
import websockets
from common import Msg


class LandsharksRover:
    commands: t.Dict[str, t.Callable[[...], t.Coroutine]] = {}

    @classmethod
    def register_command(cls, fn: t.Callable[[...], t.Coroutine]):
        cls.commands[fn.__name__] = fn

    def __init__(self):
        self.sck: t.Optional[websockets.WebSocketClientProtocol] = None
        self.current_command: t.Optional[asyncio.Task] = None

    async def main(self):
        # Open the socket connection
        await self.open_ws()
        await asyncio.gather(
            self.handle_ws(),  # Handles websocket messages
            self.maintain_ws()  # Keeps the socket open
        )

    async def open_ws(self):
        self.sck = await websockets.connect("ws://team1157.org:11571/rover", ping_interval=5, ping_timeout=10)
        await self.sck.send(json.dumps({
            "type": "special"
        }))

    async def maintain_ws(self):
        while True:
            # Monitor the connection until it gets closed, then reopen it
            await self.sck.wait_closed()
            await self.open_ws()

    async def handle_ws(self):
        try:
            async for msg_raw in self.sck:
                msg = json.loads(msg_raw)  # Fetch next message
                if msg["type"] == "command":
                    cmd = msg["command"]
                    params = msg["parameters"]
                    fn = self.commands[cmd]
                    sig = inspect.signature(fn)
                    required_params = [k for k, v in sig.parameters.items() if v.default is not inspect.Parameter.empty]
                    # Verify that all provided params are accepted by the command,
                    # and that all required params are provided
                    if not all(x in sig.parameters.keys() for x in params.keys())\
                            or not all(x in params.keys() for x in required_params):
                        await self.sck.send({
                            "id": msg["id"],
                            "status": "error",
                            "error": "command_invalid_parameters",
                            "message": "The parameters provided for the command were invalid."
                        })
                        await self.sck.send(Msg.command_response("error", ))
                        continue
                    # todo?: maybe check types of params
                    # Cancel current command if there is one
                    if self.current_command is not None:
                        self.current_command.cancel()
                    # Run command
                    self.current_command = asyncio.create_task(self.command_wrapper(fn(**params)))
                elif msg["type"] == "":
                    pass
        finally:
            pass

    async def command_wrapper(self, coro: t.Coroutine):
        # Wait for coroutine to finish
        res = await coro
        # Send command response
        await self.sck.send(Msg.command_response(
            "ok"
        ))


# TODO: Split the command definitions off into a separate file somehow
@LandsharksRover.register_command
async def ping(*, data: str = ""):
    return {"message": "pong", "data": data}  # This gets fed into


@LandsharksRover.register_command
async def move(*,
               distance: float = 0,
               angle: float = 0,
               speed: float = 0.5,
               acceleration: float = 2):
    """
    Performs a movement.
    :param distance: The distance forward, relative to the rover, to move (m)
    :param angle: The angle to rotate by throughout the movement (deg)
    :param speed: The maximum speed during the movement (m/s)
    :param acceleration: The rate to accelerate at during the movement (m/s^2)
    :return:
    """
    pass  # Translate angle+distance into differential speeds+times


@LandsharksRover.register_command
async def move_differential(*, time: float,
                            left_speed: float, left_acceleration: float,
                            right_speed: float, right_acceleration: float):
    """
    Performs a movement based on differential speeds
    :param time: The time to execute the movement (s)
    :param left_speed: (m/s)
    :param left_acceleration: (m/s^2)
    :param right_speed: (m/s)
    :param right_acceleration: (m/s^2)
    :return:
    """
    pass


@LandsharksRover.register_command
async def camera_move(*, pan: float = 0, tilt: float = 0):
    """
    Moves the camera to the specified offset from its current position.
    :param pan: The horizontal position to move to (deg)
    :param tilt: The vertical position to move to (deg)
    :return:
    """
    pass


@LandsharksRover.register_command
async def camera_move_absolute(*, pan: float, tilt: float):
    """
    Moves the camera to the specified position
    :param pan: The horizontal position to move to (deg)
    :param tilt: The vertical position to move to (deg)
    :return:
    """
    pass


@LandsharksRover.register_command
async def camera_capture():
    """
    Captures an image based on the current camera options
    :return:
    """
    pass


@LandsharksRover.register_command
async def camera_begin_stream():
    """
    Starts a livestream based on the current camera options
    :return:
    """
    pass


@LandsharksRover.register_command
async def camera_end_stream():
    """
    Ends the current livestream if it is running
    :return:
    """
    pass


@LandsharksRover.register_command
async def ssh_open_tunnel(*,
                          host: str = "1157.org", host_port: int = 22,
                          local_port: int = 22, remote_port: int = 11572):
    """
    Opens an SSH tunnel, by default opening a remote shell via the base station server
    :param host: The remote machine to tunnel
    :param host_port: The SSH port on the host
    :param local_port: The local (rover-side) port to tunnel to the host
    :param remote_port: The port to expose the local port as on the host
    :return:
    """
    p = await asyncio.create_subprocess_exec("ssh", [
        "-N",  # Don't open shell, just tunnel
        "-R", f"{remote_port}:127.0.0.1:{local_port}",  # Open reverse tunnel
        f"{host}",  # Log into remote
        "-p", f"{host_port}"
    ])


@LandsharksRover.register_command
async def ssh_close_tunnel():
    """
    Closes an SSH tunnel, if one is open
    :return:
    """
    pass