import websockets
import asyncio

viewers = set()


async def serve(sck):
    print(f"client connected: {sck.remote_address} at path {sck.path}")
    match sck.path:
        case "/view":
            viewers.add(sck)
            print("connected as viewer")
            await asyncio.Future()
        case "/stream":
            print("connected as streamer")
            async for msg in sck:
                websockets.broadcast(viewers, msg)
    print(f"client disconnected: {sck.remote_address}")


async def main():
    async with websockets.serve(serve, port=11572):
        await asyncio.Future()


if __name__ == '__main__':
    asyncio.run(main())
