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
    def command_response(contents: dict = {}, error: Error = None, id_: int = None):
        return json.dumps({
            "type": "command_response",
            "id": id_,
            "contents": contents,
            "error": (error.value if error is not None else None)
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
        if message["type"] == "command_response" and not _chk_types(message, {
            "id": int,
            "error": ("str" or type(None)),
            "contents": dict
        }):
            return False
