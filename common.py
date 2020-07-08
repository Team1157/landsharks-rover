"""
Common components used in both rover and server
"""
import json
from enum import Enum


class Error(Enum):
    """
    An enum of the possible errors that can be sent by the rover and base station
    """

    json_parse_error = "json_parse_error"
    command_invalid_parameters = "command_invalid_parameters"


class Msg:
    """
    Several utility functions for dealing with rover control messages
    """

    # Message builders
    @staticmethod
    def log(message: str, level: str):
        return json.dumps({
            "type": "log",
            "message": message,
            "level": level
        })

    @staticmethod
    def error(err: Error, message: str):
        return json.dumps({
            "type": "error",
            "error": err.value,
            "message": message
        })

    @staticmethod
    def command(command: str, parameters: dict):
        return json.dumps({
            "type": "command",
            "command": command,
            "parameters": parameters
        })

    @staticmethod
    def command_response(error: Error = None, contents: dict = {}, id_: int = None):
        return json.dumps({
            "type": "command_response",
            "error": (error.value if error is not None else None),
            "contents": contents,
            "id": id_
        })

    # Other utils
    @staticmethod
    def verify(message: dict):
        """
        Verifies that a message is valid
        :param message: The message to verify
        :return:
        """
        return True  # todo: implement
