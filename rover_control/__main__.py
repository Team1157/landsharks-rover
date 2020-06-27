import asyncio
from rover_control import LandsharksRover

rover = LandsharksRover()
asyncio.run(rover.main())
