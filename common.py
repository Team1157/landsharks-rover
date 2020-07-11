"""
Common components used in both rover and base station
"""
import json
from enum import Enum


class Error(Enum):
    """
    An enum of the possible errors that can be sent by the rover and base station
    """

    json_parse_error = "json_parse_error"
    command_invalid_parameters = "command_invalid_parameters"
    invalid_message = "invalid_message"
    id_in_use = "id_in_use"
    unknown_id = "unknown_id"


class Status(Enum):
    """
    The possible states that the rover can be in
    """
    idle = "idle"
    busy = "busy"


def _chk_types(msg: dict, checklist: dict) -> bool:
    """
    For each key in checklist, checks that msg has that key and that its type is or is in checklist[key].
    If checklist[key] is None, then just checks for key's presence but not its type
    :param msg:
    :param checklist:
    :return:
    """
    for key, types in checklist.items():
        if key not in msg:
            return False
        if types is not None:
            if type(types) is tuple and type(msg[key]) not in types:
                return False
            elif type(msg[key]) is not types:
                return False
    return True


class Msg:
    """
    Several utility functions for dealing with rover control messages
    """

    # Message builders
    @staticmethod
    def log(message: str, level: str) -> str:
        return json.dumps({
            "type": "log",
            "message": message,
            "level": level
        })

    @staticmethod
    def error(err: Error, message: str) -> str:
        return json.dumps({
            "type": "error",
            "error": err.value,
            "message": message
        })

    @staticmethod
    def command(command: str, parameters: dict) -> str:
        return json.dumps({
            "type": "command",
            "command": command,
            "parameters": parameters
        })

    @staticmethod
    def command_response(contents: dict = None, error: Error = None, id_: int = None) -> str:
        return json.dumps({
            "type": "command_response",
            "id": id_,
            "contents": (contents if contents is not None else {}),
            "error": (error.value if error is not None else None)
        })

    @staticmethod
    def status(status: Status, current_command: int = None):
        return json.dumps({
            "type": "status",
            "status": status.value,
            "current_command": current_command
        })

    @staticmethod
    def queue_status(current_command: dict, queued_commands: list) -> str:
        return json.dumps({
            "type": "queue_status",
            "current_command": current_command,
            "queued_commands": queued_commands
        })

    # Other utils
    @staticmethod
    def verify(message: dict) -> bool:
        """
        Verifies that a message is valid
        :param message: The message to verify
        :return:
        """
        if not _chk_types(message, {"type": str}):
            return False
        if message["type"] == "command" and not _chk_types(message, {"command": str, "params": dict}):
            return False
        elif message["type"] == "command_response" and not _chk_types(message, {
            "id": int,
            "error": ("str" or type(None)),
            "contents": dict
        }):
            return False
        elif message["type"] == "logs" and not _chk_types(message, {
            "message": str,
            "level": str
        }):
            return False
        elif message["type"] == "error" and not _chk_types(message, {
            "error": str,
            "message": str
        }):
            return False
        elif message["type"] == "status" and not _chk_types(message, {
            "status": str,
            "current_command": (int or type(None))
        }):
            return False
        # TODO: add more checkers
        return True
