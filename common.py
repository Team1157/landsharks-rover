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
    auth_error = "auth_error"


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

    @staticmethod
    def query_response(query: str, value) -> str:
        return json.dumps({
            "type": "query_response",
            "query": query,
            "value": value
        })

    # Other utils
    @staticmethod
    def verify(message: dict) -> bool:
        """
        Verifies that a message is valid
        :param message: The message to verify
        :return:
        """
        # NoneType reference for allowing a variable to be None
        _nonetype = type(None)
        # Always error if there is no "type" key
        if "type" not in message:
            return False
        # Verify message types
        if message["type"] == "command":
            return _chk_types(message, {
                "type": str,
                "id": int,
                "command": str,
                "parameters": dict
            })
        elif message["type"] == "clear_queue":
            return True
        elif message["type"] == "option":
            return _chk_types(message, {
                "set": dict,
                "get": dict
            })
        elif message["type"] == "log":
            return _chk_types(message, {
                "message": str,
                "level": str
            })
        elif message["type"] == "error":
            return _chk_types(message, {
                "error": str,
                "message": str
            })
        elif message["type"] == "query":
            return _chk_types(message, {
                "query": str
            })
        elif message["type"] == "e_stop":
            return True
        elif message["type"] == "command_response":
            return _chk_types(message, {
                "id": int,
                "error": (str, _nonetype),
                "contents": dict
            })
        elif message["type"] == "status":
            return _chk_types(message, {
                "status": str,
                "current_command": (int, _nonetype)
            })
        elif message["type"] == "option_response":
            return _chk_types(message, {
                "values": dict
            })
        elif message["type"] == "digest":
            return _chk_types(message, {
                "sensors": dict
            })
        elif message["type"] == "auth":
            return _chk_types(message, {
                "username": str,
                "password": str
            })
        return False
