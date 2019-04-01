import asyncio
import zmq
from zmq.asyncio import Context, Socket


async def receiver(sock: Socket):
    while True:
        print(await sock.recv_multipart())


async def main():
    ctx = Context()
    sock = ctx.socket(zmq.SUB)
    sock.connect('tcp://127.0.0.1:12345')
    sock.subscribe(b'')
    try:
        await receiver(sock)
    finally:
        sock.close(1)
        ctx.destroy()


if __name__ == '__main__':
    asyncio.run(main())
