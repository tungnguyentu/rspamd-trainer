import logging
from uuid import uuid4
from sys import stdout, stderr
from os import path

RUN_ID = str(uuid4())[:8]
DEFAULT_LOG_LEVEL = logging.INFO

def configure_logging(verbose: bool = False, debug: bool = False):
    log_dir = 'log'
    log_level = logging.DEBUG if debug else DEFAULT_LOG_LEVEL
    log_format = '%(asctime)s %(levelname)s (' + RUN_ID + ') - ' + '%(message)s'

    # Configure global logging for extended.log, including messages from 3rd party modules (e.g. managesieve3)
    logfile_extended = path.join(log_dir, 'extended.log')
    log_handlers = [logging.FileHandler(filename=logfile_extended)]
    if verbose:
        log_handlers.append(logging.StreamHandler(stdout))
    logging.basicConfig(level=log_level, format=log_format, handlers=log_handlers)

    # application.log for project specific logging
    logger = logging.getLogger('rspamd_teacher_application')
    formatter = logging.Formatter(log_format)
    logfile = path.join(log_dir, 'application.log')
    log_handler_application = logging.FileHandler(filename=logfile)
    log_handler_application.setFormatter(formatter)
    logger.addHandler(log_handler_application)

    # log messages above ERROR to stderr
    log_handler_stderr = logging.StreamHandler(stderr)
    log_handler_stderr.setLevel(logging.ERROR)
    logger.addHandler(log_handler_stderr)

    return logger
