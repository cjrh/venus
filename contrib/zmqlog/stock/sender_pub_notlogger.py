import asyncio
import zmq
from zmq.asyncio import Context, Socket

async def sender(sock: Socket):
    while True:
        await asyncio.sleep(1)
        print('.', end='', flush=True)
        await sock.send(b'blah')

async def main():
    ctx = Context()
    sock = ctx.socket(zmq.PUB)
    sock.bind('tcp://127.0.0.1:12345')
    try:
        await sender(sock)
    finally:
        sock.close(1)
        ctx.destroy()


if __name__ == '__main__':
    asyncio.run(main())

