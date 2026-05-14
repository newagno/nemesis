import os
import json
import logging
import datetime
from colorama import Fore, Style, init

# Initialize colorama
init()

class CustomFormatter(logging.Formatter):
    """Custom color formatter for console."""
    
    COLORS = {
        logging.DEBUG: Fore.CYAN,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.MAGENTA + Style.BRIGHT,
        "WAIT": Fore.BLUE,
        "TX": Fore.WHITE + Style.BRIGHT
    }

    def format(self, record):
        level_color = self.COLORS.get(record.levelno, Fore.WHITE)
        if hasattr(record, 'custom_level'):
            level_color = self.COLORS.get(record.custom_level, Fore.WHITE)
            level_name = record.custom_level
        else:
            level_name = record.levelname

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = super().format(record)
        
        return f"{Style.DIM}[{timestamp}]{Style.RESET_ALL} {level_color}[{level_name:5}]{Style.RESET_ALL} {message}"

def setup_logger(logs_dir="logs", log_name="nemesis"):
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

    logger = logging.getLogger(log_name)
    logger.setLevel(logging.DEBUG)

    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(CustomFormatter('%(message)s'))
    logger.addHandler(ch)

    # File handler (Rotating)
    from logging.handlers import RotatingFileHandler
    file_plain = os.path.join(logs_dir, f"{log_name}.log")
    fh = RotatingFileHandler(file_plain, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
    fh.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s'))
    logger.addHandler(fh)

    # JSON logging helper
    def log_json(data):
        file_json = os.path.join(logs_dir, f"{log_name}.json")
        data['timestamp'] = datetime.datetime.now().isoformat()
        with open(file_json, 'a', encoding='utf-8') as f:
            f.write(json.dumps(data) + '\n')

    # Add custom convenience methods
    def wait(msg):
        record = logger.makeRecord(logger.name, logging.INFO, None, None, msg, None, None)
        record.custom_level = "WAIT"
        logger.handle(record)

    def tx(msg):
        record = logger.makeRecord(logger.name, logging.INFO, None, None, msg, None, None)
        record.custom_level = "TX"
        logger.handle(record)

    logger.wait = wait
    logger.tx = tx
    logger.log_json = log_json

    return logger

# Singleton logger
logger = setup_logger()
