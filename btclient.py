#!/usr/bin/env python

import argparse, logging
from bt.client import Client

if __name__ == '__main__':
    # Choose log level
    LEVELS = {
            'debug': logging.DEBUG,
            'info': logging.INFO,
            'warning': logging.WARNING,
            'error': logging.ERROR,
            'critical': logging.CRITICAL
            }
    log_level = logging.DEBUG
    logger = logging.getLogger('bt')
    logger.setLevel(log_level)
    # Output logging to console
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # Run BitTorrent client
    client = Client()
    client.add_torrent("one.torrent")
    client.start()

