import logging
import typing as t
import websockets

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


class ClientsCollection:
    def __init__(self, clients: t.Dict[str, t.Set[websockets.WebSocketServerProtocol]] = None):
        if not clients:
            clients = {}
        self.clients = clients

    def with_role(self, role: str) -> t.Set[websockets.WebSocketServerProtocol]:
        if role not in self.clients:
            self.clients[role] = set()
        return self.clients[role]

    def get_role(self, sck: websockets.WebSocketServerProtocol) -> t.Optional[str]:
        for role, clients in self.clients.items():
            if sck in clients:
                return role
        return None

    def add(self, sck: websockets.WebSocketServerProtocol, role: str):
        self.with_role(role).add(sck)

    def remove(self, sck: websockets.WebSocketServerProtocol):
        for cl in self.clients.values():
            if sck in cl:
                cl.remove(sck)

    def all(self):
        cl = set()
        for r in self.clients.values():
            cl = cl.union(r)
        return cl

    def __iter__(self):
        return self.all().__iter__()

    def __bool__(self):
        return len(self) > 0

    def __len__(self):
        return len(self.all())

    def __contains__(self, item):
        return item in self.all()
