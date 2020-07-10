import asyncio
import websockets
from base_station import RoverBaseStation

station = RoverBaseStation()
# asyncio.run(websockets.serve(station.serve, "localhost", 11571))
asyncio.get_event_loop().run_until_complete(websockets.serve(station.serve, "localhost", 11571))
asyncio.get_event_loop().run_forever()