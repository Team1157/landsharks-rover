import typing as t
import asyncio
import serial_asyncio


class SerialProtocol(asyncio.Protocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.transport: t.Optional[serial_asyncio.SerialTransport] = None

    def connection_made(self, transport: serial_asyncio.SerialTransport) -> None:
        print("Serial connected")
        self.transport = transport

    def connection_lost(self, exc: t.Optional[Exception]) -> None:
        print("Serial disconnected")

    def data_received(self, data: bytes) -> None:
        pass