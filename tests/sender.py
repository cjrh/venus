"""
Main program that will send logs
"""
import argparse
import contextlib
import logging
import time
from collections import defaultdict
from functools import partial

import logjson
import zmq
from zmq.log.handlers import PUBHandler

logger = logging.getLogger()


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
    for i in range(int(iterations)):
        logger.info('This is a test')
        time.sleep(delay)


def main(args):
    with make_sock() as sock:
        sock.connect(f'tcp://{args.hostname}:{args.port}')
        setup_logging(sock)
        app(args.iterations)


if __name__ == '__main__':
    logging.basicConfig(level='DEBUG')
    parser = argparse.ArgumentParser()
    parser.add_argument('-H', '--hostname', default='localhost')
    parser.add_argument('-p', '--port', default=12345)
    parser.add_argument('-i', '--iterations', default=10)
    args = parser.parse_args()
    main(args)
