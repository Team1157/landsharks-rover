"""
Common components used in both rover and server
"""
import json


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
    def error(err: str, message: str) -> str:
        return json.dumps({
            "type": "error",
            "error": err,
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
    def command_response(status: str, contents: dict = None, id_: int = None) -> str:
        return json.dumps({
            "type": "command_response",
            "id": id_,
            "status": status,
            "contents": contents
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
