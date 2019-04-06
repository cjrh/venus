import logging
import json
import asyncio
from biodome import environ
import consul.aio


logger = logging.getLogger(__name__)

DO_NOT_PRINT = {'password', 'pass', 'pw'}

HEALTH_CHECK_PORT = environ.get('HEALTH_CHECK_PORT', 5000)
HEALTH_CHECK_HOST = environ.get('HEALTH_CHECK_HOST', '0.0.0.0')

START_LOG_LEVEL = environ.get('START_LOG_LEVEL', 'DEBUG')

ENABLE_CONSUL_REFRESH = environ.get_callable('ENABLE_CONSUL_REFRESH', True)
CONSUL_HTTP_ADDR = environ.get('CONSUL_HTTP_ADDR', 'localhost:8500')
CONSUL_ENV_KV_PATH = environ.get('CONSUL_ENV_KV_PATH', 'venus/config')
CONSUL_LOGLEVELS_KV_PATH = environ.get('CONSUL_ENV_LOGLEVELS_PATH', 'venus/logging')
UPDATE_ENV_VAR_INTERVAL_SECONDS = environ.get_callable(
    'UPDATE_ENV_VAR_INTERVAL_SECONDS', 60.0
)

VENUS_PORT = environ.get_callable('VENUS_PORT', 56119)
DROP_FIELDS = environ.get_callable(
    'DROP_FIELDS', [
        'stack_info',
        'funcName',
        'created',
        'msecs',
        'module',
        'thread',
        'threadName',
        'processName',
    ]
)

MAX_BATCH_SIZE = environ.get_callable('MAX_BATCH_SIZE', 100)
MAX_BATCH_AGE_SECONDS = environ.get_callable(
    'MAX_BATCH_AGE_SECONDS', 5)


async def refresh_from_configuration():
    """Long-running task for live-loading config"""
    logger.debug('Loaded CONSUL_HTTP_ADDR=%s', CONSUL_HTTP_ADDR)
    host, port = [_.strip() for _ in CONSUL_HTTP_ADDR.split(':')]
    port = int(port)

    c = consul.aio.Consul(
        host=host,
        port=port,
        scheme='http',
        verify=False
    )

    while True:
        try:
            if ENABLE_CONSUL_REFRESH():
                await load_new_env_vars(c)
                await load_new_logger_levels(c)
            await asyncio.sleep(UPDATE_ENV_VAR_INTERVAL_SECONDS())
        except asyncio.CancelledError:
            logger.info('Refresh from consul task cancelled.')
            c.close()
            return
        except:
            logger.exception('Problem during update from Consul')
            await asyncio.sleep(UPDATE_ENV_VAR_INTERVAL_SECONDS())


async def load_new_env_vars(consul: consul.aio.Consul):
    try:
        index, key_data = await consul.kv.get(CONSUL_ENV_KV_PATH)
        if not key_data:
            logger.debug(f'No environment config defined at '
                         f'{CONSUL_ENV_KV_PATH}. Skipping.')
            return
        data = key_data['Value']
        env_data = json.loads(data.decode('utf-8'))
        # Extract the items with common keys from current env
        current = {k: environ.get(k) for k in env_data}
        for k, v in env_data.items():
            if str(v) == current[k]:
                continue
            current_value = current[k]
            new_value = v
            # Password protection
            if any(unprintable in k.lower() for unprintable in DO_NOT_PRINT):
                current_value = current_value[0] + 'X' * len(current_value[1:])
                new_value = new_value[0] + 'X' * len(new_value[1:])
            logger.info(
                'Env var "%s" changed on Consul. Was "%s", '
                'updating to "%s"', k, current_value, new_value
            )
            try:
                environ[k] = str(v)
            except ValueError:
                logger.exception(f'Problem updating {k}')
    except:
        logger.exception('Error when updating env vars')


async def load_new_logger_levels(consul: consul.aio.Consul):
    try:
        index, key_data = await consul.kv.get(CONSUL_LOGLEVELS_KV_PATH)
        if not key_data:
            logger.debug(f'No logging config defined at '
                         f'{CONSUL_LOGLEVELS_KV_PATH}. Skipping.')
            return
        data = key_data['Value']
        logger_levels = json.loads(data.decode('utf-8'))
        for name, new_level in logger_levels.items():  # type: str, str
            if name == 'root':
                name = None
            name_logger = logging.getLogger(name)
            old_level = logging.getLevelName(name_logger.level)  # type: str
            if new_level == old_level:
                continue

            logger.info(
                'Logger "%s" changed from level "%s" to "%s"',
                name or 'root', old_level, new_level
            )
            name_logger.setLevel(logging.getLevelName(new_level))
    except:
        logger.exception('Error when updating logging config')
