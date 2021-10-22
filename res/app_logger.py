import logging
from logging.config import fileConfig, dictConfig

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': {
        'default': {
            'level': 'INFO',
            'formatter': 'standard',
            'class': 'logging.FileHandler',
            'filename': '/var/log/xrdp-user/backup_service.log',
        },
    },
    'loggers': {
        '': {  # root res
            'handlers': ['default'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}


def get_logger(name):
    # fileConfig('log_config.ini')
    dictConfig(LOGGING_CONFIG)
    logger = logging.getLogger(name)
    return logger


if __name__ == '__main__':
    log = get_logger(__name__)
    log.critical('test')
