# (c) 2022 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
# This AWS Content is provided subject to the terms of the AWS Customer Agreement
# available at http://aws.amazon.com/agreement or other written agreement between
# Customer and Amazon Web Services, Inc.

import logging
import os


class CustomLogger ():
    def __init__(self, event=None):
        log_level = os.getenv('LOG_LEVEL', 'INFO')
        self._logger = logging.getLogger()
        self._logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        logging.getLogger("botocore").setLevel(logging.ERROR)
        logging.debug("initiate logger")

    @property
    def logger(self):
        return self._logger
