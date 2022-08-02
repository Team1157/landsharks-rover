import asyncio
from base_station import RoverBaseStation

station = RoverBaseStation()

asyncio.run(station.main())
