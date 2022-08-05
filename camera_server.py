import websockets
import asyncio

viewers = set()


async def serve(sck):
    match sck.path:
        case "view":
            viewers.add(sck)
            print(f"new viewer: {sck.remote_address}")
            await asyncio.Future()
        case "stream":
            print(f"new streamer: {sck.remote_address}")
            async for msg in sck:
                await websockets.broadcast(viewers, msg)


async def main():
    async with websockets.serve(serve, port=11572):
        await asyncio.Future()


if __name__ == '__main__':
    asyncio.run(main())
