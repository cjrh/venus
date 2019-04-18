"""
Main program that will send logs
"""
import argparse
import contextlib
import logging
import time
from collections import defaultdict

import biodome
import logjson
import zmq
from zmq.log.handlers import PUBHandler

logger = logging.getLogger('sender')


@contextlib.contextmanager
def make_sock():
    """
    NOTE: this is a PUSH socket, not pub.
    :return:
    """
    ctx = zmq.Context()
    sock: zmq.Socket = ctx.socket(zmq.PUSH)
    # Buffer up to 1000 log messages only, and drop any further messages

    # sock.setsockopt(zmq.SNDHWM, 10)
    # This will fail currently. Need to handle zmq.error.Again that gets
    # raise from the send inside the pubhandler. Will probably have to
    # make our own version of this pubhandler.
    # sock.send_multipart = partial(sock.send_multipart, flags=zmq.DONTWAIT)

    try:
        yield sock
    finally:
        sock.close(1)
        ctx.destroy()


def setup_logging(sock):
    handler = PUBHandler(sock)
    handler.setLevel('INFO')
    # Override all the level formatters to use JSON
    handler.formatters = defaultdict(logjson.JSONFormatter)
    logger.addHandler(handler)


def app(iterations, delay=1.0):
    for i in range(iterations):
        logger.info('This is a test')
        time.sleep(delay)


def app_items(items, delay=1.0):
    for item in items:
        if isinstance(item, dict) and 'message' in item:
            message = item.pop('message')
            logger.info(message, extra=item)
        else:
            logger.info(item)
        time.sleep(delay)


def main(args):
    SENDER_ITEMS = biodome.environ.get('SENDER_ITEMS', [])
    with make_sock() as sock:
        conn_str = f'tcp://{args.hostname}:{args.port}'
        logger.info(f'Connecting to {conn_str}')
        sock.connect(conn_str)
        setup_logging(sock)
        if SENDER_ITEMS:
            app_items(SENDER_ITEMS, args.delay)
        else:
            app(args.iterations, args.delay)


if __name__ == '__main__':
    logging.basicConfig(level='DEBUG')
    parser = argparse.ArgumentParser()
    parser.add_argument('-H', '--hostname', default='localhost')
    parser.add_argument('-p', '--port', default=12345)
    parser.add_argument('-i', '--iterations', default=10, type=int)
    parser.add_argument('-d', '--delay', default=1.0, type=float)
    args = parser.parse_args()
    main(args)
