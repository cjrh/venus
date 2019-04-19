import logging
import asyncio
import zmq

from contextlib import contextmanager
from typing import List
from zmq.asyncio import Context, Socket

from .. import settings
from .. import models

"""
ZMQ socket options:


ZMQ_MAXMSGSIZE: Maximum acceptable inbound message size
Limits the size of the inbound message. If a peer sends a message larger than ZMQ_MAXMSGSIZE it is disconnected. Value of -1 means no limit.
Option value type 	int64_t
Option value unit 	bytes
Default value 	-1
Applicable socket types 	all


ZMQ_RCVHWM: Set high water mark for inbound messages
The ZMQ_RCVHWM option shall set the high water mark for inbound messages on the specified socket. The high water mark is a hard limit on the maximum number of outstanding messages ØMQ shall queue in memory for any single peer that the specified socket is communicating with. A value of zero means no limit.
If this limit has been reached the socket shall enter an exceptional state and depending on the socket type, ØMQ shall take appropriate action such as blocking or dropping sent messages. Refer to the individual socket descriptions in zmq_socket(3) for details on the exact action taken for each socket type.
Option value type 	int
Option value unit 	messages
Default value 	1000
Applicable socket types 	all

ZMQ_SNDHWM: Set high water mark for outbound messages

The ZMQ_SNDHWM option shall set the high water mark for outbound messages on the specified socket. The high water mark is a hard limit on the maximum number of outstanding messages ØMQ shall queue in memory for any single peer that the specified socket is communicating with. A value of zero means no limit.
Option value type 	int
Option value unit 	messages
Default value 	1000
Applicable socket types 	all

"""


CONTEXT: zmq.Context = None
logger = logging.getLogger(__name__)


@contextmanager
def zmq_context() -> Context:
    """Intended to be called from outside the event loop scope, e.g.,
    around `aiorun.run(amain())`"""
    global CONTEXT
    logger.info('Creating ZMQ context.')
    CONTEXT = Context.instance()
    try:
        yield CONTEXT
    finally:
        logger.info('Terminating ZMQ context')
        CONTEXT.destroy()
        logger.info('ZMQ context terminated.')


def apply_tcp_sock_options(sock: Socket):
    sock.setsockopt(zmq.LINGER, 1)


async def zmq_connection_manager(pull_queue: asyncio.Queue):
    loop = asyncio.get_event_loop()
    logger.debug('Starting pull socket')
    pull_task = loop.create_task(pull_sock(pull_queue))

    try:
        await pull_task
    except asyncio.CancelledError:
        logger.info("zmq_connection_manager was cancelled. It's probably "
                    "shutdown time.")


async def pull_sock(q: asyncio.Queue) -> None:
    """This routine exists for one purpose only, and that is to place
    incoming IO messages onto the given queue."""
    sock: Socket = CONTEXT.socket(zmq.PULL)
    apply_tcp_sock_options(sock)
    logger.info(f'Venus binding on port {settings.VENUS_PORT()}')
    sock.bind(f'tcp://*:{settings.VENUS_PORT():d}')

    try:
        logger.debug('Waiting for data on pull socket')
        while True:
            raw: List[bytes] = await sock.recv_multipart()
            logger.debug(f'Received a message! {raw}')
            try:
                msg = models.Message(*raw)
            except TypeError:
                logger.exception(f'Unexpected message received: {raw}')
                continue

            # Cannot block on the queue. Backpressure cannot be
            # applied for this application, because the source of
            # the data is application logging and that cannot be
            # slowed down. We have to drop, thus, use the nowait
            # version.
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                logger.error(f'Receive queue full. Dropping message: {msg}')
    finally:
        logger.info('Closing push sock')
        sock.close(1)
