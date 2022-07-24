import logging
import typing as t
import websockets
from common import Role

# Numeric logging levels as defined by `logging`
LOG_LEVELS = {
    "critical": logging.CRITICAL,
    "fatal": logging.FATAL,
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "warn": logging.WARN,
    "info": logging.INFO,
    "debug": logging.DEBUG
}


class Client:
    def __init__(self, sck: websockets.WebSocketServerProtocol, user: str, role: Role):
        self.sck = sck
        self.user = user
        self.role = role

    @property
    def ip(self) -> str:
        return self.sck.remote_address[0]