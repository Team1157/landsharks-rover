import asyncio
import websockets
import ssl
from base_station import RoverBaseStation

station = RoverBaseStation()

kwargs = {
    "host": station.config.server.host,
    "port": station.config.server.port
}

if station.config.wss.enabled:
    ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_ctx.load_cert_chain(station.config.wss.chain_path, station.config.wss.privkey_path)
    kwargs["ssl"] = ssl_ctx

asyncio.get_event_loop().run_until_complete(websockets.serve(station.serve, **kwargs))
asyncio.get_event_loop().run_forever()
