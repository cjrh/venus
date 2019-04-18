import argparse
import asyncio
import logging
import sys
from weakref import WeakValueDictionary

import aiohealthcheck
import aiologfields
import aiorun
import biodome

import venus.db.write
from venus import db
from venus import io
from venus import settings

logger = logging.getLogger(__name__)


async def amain(args) -> WeakValueDictionary:
    """Start up all the long-running tasks and then return.
    The tasks typically communicate with each other via queues that
    are set up here."""
    loop = asyncio.get_event_loop()
    tasks_created = WeakValueDictionary()

    tasks_created['db_pool'] = loop.create_task(db.activate())

    logger.info('Task: live-loading env vars and logging levels')
    tasks_created['config'] = loop.create_task(settings.refresh_from_configuration())

    # The PULL queue is used to transfer incoming API calls from the
    # IO layer over to the DB layer.
    pull_queue = asyncio.Queue(maxsize=65536)
    tasks_created['zmq'] = loop.create_task(io.zmq_connection_manager(pull_queue))
    tasks_created['db_writer'] = loop.create_task(venus.db.write.collect(pull_queue))

    logger.info('Task: starting up health check listener')
    tasks_created['healthcheck'] = loop.create_task(
        aiohealthcheck.tcp_health_endpoint(
            port=settings.HEALTH_CHECK_PORT,
            host=settings.HEALTH_CHECK_HOST,
            payload=lambda: 'ok'
        )
    )

    return tasks_created


def main():
    aiologfields.install()
    # TODO: use kubectl to connect to a running container in DEV
    # and investigate what environment variables are available.
    # We might be able to add some of those to logrecords, e.g.
    # the k8s pod name, node name, app version, etc.

    logging.basicConfig(level='DEBUG', stream=sys.stdout)
    parser = argparse.ArgumentParser()
    parser.add_argument('--zmqport', type=int, default=None)
    args, unknown = parser.parse_known_args()
    if args.zmqport is not None:
        biodome.environ['VENUS_PORT'] = args.zmqport

    if unknown:
        logger.warning(f'Unexpected parameters given: {unknown}')

    with io.zmq_context():
        aiorun.run(amain(args))

    # This is for tests only.
    return 'main_exit'


if __name__ == "__main__":
    main()
