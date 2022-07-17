import asyncio
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

asyncio.run(station.main(**kwargs))
