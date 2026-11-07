import inspect
import logging


_CLASSNAME_CACHE = {}
_FACTORY_INSTALLED = False


def _ensure_classname_factory():
    global _FACTORY_INSTALLED
    if _FACTORY_INSTALLED:
        return

    original_factory = logging.getLogRecordFactory()

    def classname_factory(*args, **kwargs):
        record = original_factory(*args, **kwargs)
        key = (record.pathname, record.funcName, record.lineno)
        classname = _CLASSNAME_CACHE.get(key)
        if classname is None:
            classname = record.module
            frame = inspect.currentframe()
            try:
                current = frame
                # Skip factory frames
                while current and current.f_code.co_filename == __file__:
                    current = current.f_back
                while current:
                    if (
                        current.f_code.co_filename == record.pathname
                        and current.f_code.co_name == record.funcName
                    ):
                        instance = current.f_locals.get("self")
                        if instance is not None:
                            classname = instance.__class__.__name__
                        else:
                            cls_obj = current.f_locals.get("cls")
                            if isinstance(cls_obj, type):
                                classname = cls_obj.__name__
                        break
                    current = current.f_back
            finally:
                del frame
                # Avoid reference cycles
                if 'current' in locals():
                    del current
            _CLASSNAME_CACHE[key] = classname

        record.classname = classname
        return record

    logging.setLogRecordFactory(classname_factory)
    _FACTORY_INSTALLED = True


class LoggingConf:
    @staticmethod
    def get(file_name, process_name):
        _ensure_classname_factory()
        return {
            'version': 1,
            'loggers': {
                '': {  # root logger
                    'level': 'NOTSET',
                    'handlers': ['debug_console_handler', 'info_rotating_file_handler'],
                },
                'websockets': {
                    'level': 'WARNING',
                    'propagate': False,
                    'handlers': ['debug_console_handler', 'info_rotating_file_handler'],
                },
            },
            'handlers': {
                'debug_console_handler': {
                    'level': 'INFO',
                    'formatter': 'info',
                    'class': 'logging.StreamHandler',
                    'stream': 'ext://sys.stdout',
                },
                'info_rotating_file_handler': {
                    'level': 'INFO',
                    'formatter': 'info',
                    'class': 'logging.handlers.TimedRotatingFileHandler',
                    'filename': file_name,
                    'when': 'midnight',
                    'interval': 2,
                    'backupCount': 100
                }
            },
            'formatters': {
                'info': {
                    'class': 'colorlog.ColoredFormatter',
                    'format': '%(asctime)s {} %(classname)s %(funcName)s |%(lineno)s: %(levelname)s%(log_color)s %(message)s%(reset)s'.format(
                        process_name)
                }
            },
        }

    @staticmethod
    def get_test():
        _ensure_classname_factory()
        return {
            'version': 1,
            'loggers': {
                '': {  # root logger
                    'level': 'NOTSET',
                    'handlers': ['debug_console_handler'],
                },
            },
            'handlers': {
                'debug_console_handler': {
                    'level': 'INFO',
                    'formatter': 'info',
                    'class': 'logging.StreamHandler',
                    'stream': 'ext://sys.stdout',
                }
            },
            'formatters': {
                'info': {
                    'class': 'colorlog.ColoredFormatter',
                    'format': '%(asctime)s %(classname)s %(funcName)s |%(lineno)s: %(log_color)s%(message)s%(reset)s'
                }
            },
        }
