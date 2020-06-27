"""
Common components used in both rover and server
"""
import json


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
    def error(err: str, message: str):
        return json.dumps({
            "type": "error",
            "error": err,
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
    def response(status, contents: dict = None, id_: int = None):
        return json.dumps({
            "type": "response",
            "status": status,
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
