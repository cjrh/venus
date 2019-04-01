import time
import logging
import zmq
from zmq.log.handlers import PUBHandler
import logjson
from collections import defaultdict

# In this demo, we create our own socket.
ctx = zmq.Context()
socket = ctx.socket(zmq.PUB)
socket.connect('tcp://127.0.0.1:12345')

handler = PUBHandler(socket)
handler.setLevel('INFO')
# Override all the level formatters to use JSON
handler.formatters = defaultdict(logjson.JSONFormatter)

logging.basicConfig(level='DEBUG')
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)

for i in range(100):
    logger.info('blah')
    time.sleep(1)
