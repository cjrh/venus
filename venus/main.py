import sys
import argparse
import asyncio
import logging
import aiorun
import biodome
import aiologfields
import aiohealthcheck

from venus import db
import venus.db.write
from . import io
from . import settings

logger = logging.getLogger(__name__)


async def amain(args):
    """Start up all the long-running tasks. The tasks typically communicate
    with each other via queues...mostly. """
    loop = asyncio.get_event_loop()

    logger.info('Task: live-loading env vars and logging levels')
    loop.create_task(settings.refresh_from_configuration())

    # The PULL queue is used to transfer incoming API calls from the
    # IO layer over to the DB layer.
    pull_queue = asyncio.Queue(maxsize=65536)
    loop.create_task(io.zmq_connection_manager(pull_queue))
    loop.create_task(venus.db.write.collect(pull_queue))

    logger.info('Task: starting up health check listener')
    loop.create_task(
        aiohealthcheck.tcp_health_endpoint(
            port=settings.HEALTH_CHECK_PORT,
            host=settings.HEALTH_CHECK_HOST,
            payload=lambda: 'ok'
        )
    )


def main():
    aiologfields.install()
    # TODO: use kubectl to connect to a running container in DEV
    # and investigate what environment variables are available.
    # We might be able to add some of those to logrecords, e.g.
    # the k8s pod name, node name, app version, etc.

    """ Entry point """
    ENABLE_LOGSTASH = biodome.environ.get('ENABLE_LOGSTASH', False)
    if ENABLE_LOGSTASH:
        from logstash_formatter import LogstashFormatterV1
        logger = logging.getLogger()
        logger.setLevel(settings.START_LOG_LEVEL)
        handler = logging.StreamHandler(stream=sys.stdout)
        formatter = LogstashFormatterV1()
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    else:
        logging.basicConfig(level='DEBUG', stream=sys.stdout)

    parser = argparse.ArgumentParser()
    args, unknown = parser.parse_known_args()

    with io.zmq_context():
        aiorun.run(amain(args))

    # This is for tests only.
    return 'main_exit'


if __name__ == "__main__":
    main()
