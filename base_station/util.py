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


class Client:
    def __init__(self, sck: websockets.WebSocketServerProtocol, username: t.Optional[str], role: str):
        self.sck: websockets.WebSocketServerProtocol = sck
        self.username: t.Optional[str] = username
        self.role: str = role


class ClientsCollection:
    def __init__(self, clients: t.Set[Client] = None):
        if not clients:
            clients = set()
        self.clients: t.Set[Client] = clients

    def with_role(self, role: str) -> t.Set[Client]:
        if role not in self.clients:
            self.clients[role] = set()
        return self.clients[role]

    def get_role(self, client: Client) -> t.Optional[str]:
        for role, clients in self.clients.items():
            if client in clients:
                return role
        return None

    def get_client(self, sck: websockets.WebSocketServerProtocol) -> t.Optional[Client]:
        for client in self.all():
            if sck == client.sck:
                return client
        return None

    def add(self, client: Client, role: str):
        self.with_role(role).add(client)

    def remove(self, client: Client):
        for cl in self.clients.values():
            if client in cl:
                cl.remove(client)

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
        # item is a Client and is in the collection
        if item in self.all():
            return True

        # Check if item is a socket and belongs to one of the clients
        for client in self.all():
            if item == client.sck:
                return True
        return False