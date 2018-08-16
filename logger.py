import logging
import logging.handlers
from logging import NullHandler
import yaml
import os, sys

ERROR = logging.ERROR
WARNING = logging.WARNING
INFO = logging.INFO
DEBUG = logging.DEBUG
DB = 5

LOG_DIR = "logs"
LOG_SIZE = 10.0
LOG_NR = 20

dateTimeFormat = '%Y-%m-%d %H:%M:%S'

class Logger(object):
    
    def __init__(self):
        self.logger = logging.getLogger('resolver')
        
        self.loggers = [
            logging.getLogger('resolver')
        ]
        
        self.console_logging = False
        self.file_logging = False
        self.debug_logging = False
        self.database_logging = False
        self.log_file = None

        self.submitter_running = False
        
    def init_logging(self, console_logging=False, file_logging=False, debug_logging=False, database_logging=False):
        self.log_file = self.log_file or os.path.join(LOG_DIR, 'resolver.log')
        
        global log_file
        log_file = self.log_file

        self.debug_logging = debug_logging
        self.console_logging = console_logging
        self.file_logging = file_logging
        self.database_logging = database_logging

        #logging.getLogger().addHandler(NullHandler())  # nullify root logger

#         # set custom root logger
#         for logger in self.loggers:
#             if logger is not self.logger:
#                 logger.root = self.logger
#                 logger.parent = self.logger

        log_level = DB if self.database_logging else DEBUG if self.debug_logging else INFO

        # set minimum logging level allowed for loggers
        for logger in self.loggers:
            logger.setLevel(log_level)
        
        # console log handler
        if self.console_logging:
            console = logging.StreamHandler()
            console.setFormatter(logging.Formatter('%(asctime)s %(levelname)s::%(message)s', '%H:%M:%S'))
            console.setLevel(ERROR)

            for logger in self.loggers:
                logger.addHandler(console)

        # rotating log file handler
        if self.file_logging:
            rfh = logging.handlers.RotatingFileHandler(
                self.log_file, maxBytes=int(LOG_SIZE * 1048576), backupCount=LOG_NR, encoding='utf-8'
            )
            rfh.setFormatter(logging.Formatter('%(asctime)s %(levelname)-8s %(message)s', dateTimeFormat))
            rfh.setLevel(log_level)

            for logger in self.loggers:
                logger.addHandler(rfh)    
        
    def log(self, message, level=INFO, *args, **kwargs):
        try:
            if level == ERROR:
                self.logger.exception(message, *args, **kwargs)
            else:
                self.logger.log(level, message, *args, **kwargs)
        except Exception as e:
            if msg and msg.strip():  # Otherwise creates empty messages in log...
                print(msg.strip())

class Wrapper(object):
   
    instance = Logger()

    def __init__(self, wrapped):
        self.wrapped = wrapped

    def __getattr__(self, name):
        try:
            return getattr(self.wrapped, name)
        except AttributeError:
            return getattr(self.instance, name)

_globals = sys.modules[__name__] = Wrapper(sys.modules[__name__])  # pylint: disable=invalid-name
        
def init_logging(*args, **kwargs):
    return Wrapper.instance.init_logging(*args, **kwargs)
               
def log(*args, **kwargs):
    return Wrapper.instance.log(*args, **kwargs)