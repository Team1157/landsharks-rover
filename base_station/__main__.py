import asyncio
import websockets
import ssl
import toml
from base_station import RoverBaseStation
from base_station.config import Config

with open("config.toml") as f:
    config = Config(toml.load(f))

station = RoverBaseStation(config)

kwargs = {
    "host": config.server.host,
    "port": config.server.port
}

if config.wss.enabled:
    ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_ctx.load_cert_chain(config.wss.chain_path, config.wss.privkey_path)
    kwargs["ssl"] = ssl_ctx

asyncio.get_event_loop().run_until_complete(websockets.serve(station.serve, **kwargs))
asyncio.get_event_loop().run_forever()
