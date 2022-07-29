"""
Common components used in both rover and base station
"""
from enum import Enum
import typing as t

# noinspection PyUnresolvedReferences
import serde.tags
import serde.fields
import websockets


class Role(Enum):
    DRIVER = 0
    ROVER = 1

    @classmethod
    def from_path(cls, path: str) -> t.Optional["Role"]:
        match path:
            case "/driver":
                return Role.DRIVER
            case "/rover":
                return Role.ROVER
        return None


# Serialization shim to customize the type tag
class Tag(serde.tags.Internal):
    def lookup_tag(self, variant):
        # return getattr(getattr(variant, "Meta"), "tag_name", super().lookup_tag(variant))
        return getattr(variant, "tag_name", super().lookup_tag(variant))


# COMMANDS #


class Command(serde.Model):
    class Meta:
        abstract = True
        tag = Tag(tag="type")

    def to_arduino(self) -> bytes: raise NotImplementedError


class MoveDistanceCommand(Command):
    """Moves a specified distance at the specified speed while turning the specified angle over that distance"""
    tag_name = "move_distance"

    distance: serde.fields.Float()
    speed: serde.fields.Float()
    angle: serde.fields.Float()

    def to_arduino(self): return f"d{self.distance} {self.speed} {self.angle}".encode()  # TODO


class MoveContinuousCommand(Command):
    """Moves continuously at the specified speed while turning at specified angle"""
    tag_name = "move_continuous"

    speed: serde.fields.Float()
    angle: serde.fields.Float()

    def to_arduino(self): return f"c{self.speed} {self.angle}".encode()  # TODO


# MESSAGES #

class Message(serde.Model):
    """The base message type."""
    tag_name = "__INVALID__"

    class Meta:
        abstract = True
        tag = Tag(tag="type")


class EStopMessage(Message):
    """Emergency stop: immediately halts motors and cancels the current command"""
    tag_name = "e_stop"


class LogMessage(Message):
    """Writes a human-readable message to the logger"""
    tag_name = "log"

    message: serde.fields.Str()
    level: serde.fields.Str()


class CommandMessage(Message):
    """Sets the current command"""
    tag_name = "command"

    command: serde.fields.Optional(serde.fields.Nested(Command))


class CommandEndedMessage(Message):
    """Notifies that the current command has ended"""
    tag_name = "command_ended"

    command: serde.fields.Nested(Command)
    completed: serde.fields.Bool()


class CommandStatusMessage(Message):
    """Notifies of the current running command"""
    tag_name = "command_status"

    command: serde.fields.Optional(serde.fields.Nested(Command))


class AuthMessage(Message):
    """Authenticates the current client to the base station"""
    tag_name = "auth"

    token: serde.fields.Str()


class AuthResponseMessage(Message):
    """Notifies whether authentication was successful or not"""
    tag_name = "auth_response"

    success: serde.fields.Bool()
    user: serde.fields.Optional(serde.fields.Str())


class OptionMessage(Message):
    """Sets or gets options"""
    tag_name = "option"

    get: serde.fields.List(element=serde.fields.Str())
    set: serde.fields.Dict(key=serde.fields.Str())


class OptionResponseMessage(Message):
    """Returns option values set or get"""
    tag_name = "option_response"

    values: serde.fields.Dict()


class SensorDataMessage(Message):
    """Reports a sensor reading"""
    tag_name = "sensor_data"

    time: serde.fields.Int()
    sensor: serde.fields.Str()
    measurements: serde.fields.Dict(key=serde.fields.Str())


class QueryBaseMessage(Message):
    """Retrieves a value from the base station"""
    tag_name = "query_base"

    query: serde.fields.Str()


class QueryBaseResponseMessage(Message):
    """Returns a requested value from the base station"""
    tag_name = "query_base_response"

    query: serde.fields.Str()
    value: None


class PointCameraMessage(Message):
    """Sets the target camera pointing direction"""
    tag_name = "point_camera"

    yaw: serde.fields.Int()
    pitch: serde.fields.Int()
    relative: serde.fields.Bool() = False


class ArduinoDebugMessage(Message):
    """Sends a raw message to the Arduino"""
    tag_name = "arduino_debug"

    message: serde.fields.Bytes()


# Extension method

def send_msg(self: websockets.WebSocketCommonProtocol, msg: Message):
    return self.send(msg.to_json())


websockets.WebSocketCommonProtocol.send_msg = send_msg
del send_msg


__all__ = [
    "Role",
    "Command",
    "MoveDistanceCommand",
    "MoveContinuousCommand",
    "Message",
    "EStopMessage",
    "LogMessage",
    "CommandMessage",
    "CommandEndedMessage",
    "CommandStatusMessage",
    "AuthMessage",
    "AuthResponseMessage",
    "OptionMessage",
    "OptionResponseMessage",
    "SensorDataMessage",
    "QueryBaseMessage",
    "QueryBaseResponseMessage",
    "PointCameraMessage",
    "ArduinoDebugMessage"
]
