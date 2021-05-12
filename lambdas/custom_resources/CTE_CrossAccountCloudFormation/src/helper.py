# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
import time
import re
from functools import wraps

logging.basicConfig()
logger = logging.getLogger()
logging.getLogger("botocore").setLevel(logging.ERROR)
logger.setLevel(logging.INFO)


def retry_v2(max_attempts: int = 5, delay: int = 3, error_code='TooManyRequestsException', error_message='None'):
    """retry and

    Args:
        max_attempts (int): Max number of retries
        delay (int): Duration to wait before another retry
        error_code (str): Error code to search for in error
        error_message (str): Error message to search for to retry

    Returns:
        :obj:`json`: Returns json object (dict) of the user parameters
    """

    def retry_decorator(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            m_attempts = max_attempts  # create new memory allocation
            while m_attempts > 1:
                try:
                    return function(*args, **kwargs)

                except Exception as e:
                    logger.warning(e)
                    if error_message and re.search(error_message, str(e)):
                        logger.warning(
                            f"Definition failed:{function.__name__} with '{error_message}' message, trying again "
                            f"in {delay} seconds..."
                        )
                        time.sleep(delay)
                        m_attempts -= 1
                        last_exception = e

                    elif e.response['Error']['Code'] == error_code:
                        logger.warning(
                            f"Definition failed:{function.__name__} with '{error_code}' error code, trying again "
                            f"in {delay} seconds..."
                        )
                        time.sleep(delay)
                        m_attempts -= 1
                        last_exception = e

                    else:
                        raise e

            logger.error(f"Was not successfully able to complete the request after {max_attempts} attempts")
            raise last_exception

        return wrapper

    return retry_decorator
