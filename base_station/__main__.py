import asyncio
import websockets
import ssl
from base_station import RoverBaseStation

station = RoverBaseStation()
# ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
# ssl_ctx.load_cert_chain()

asyncio.get_event_loop().run_until_complete(websockets.serve(
    station.serve,
    "localhost",
    11571,
    # ssl=ssl_ctx
))
asyncio.get_event_loop().run_forever()
