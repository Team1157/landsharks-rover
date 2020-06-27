import asyncio
import websockets
from base_station import RoverBaseStation

station = RoverBaseStation()
asyncio.run(websockets.serve(station.serve, "localhost", 11571))
