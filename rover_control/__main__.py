import asyncio
from rover_control import Sandshark

rover = Sandshark()
asyncio.run(rover.main())
