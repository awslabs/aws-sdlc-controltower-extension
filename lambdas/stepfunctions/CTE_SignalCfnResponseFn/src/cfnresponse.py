# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from __future__ import print_function
import logging
import os
import json
import urllib3

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOGGER = logging.getLogger()
LOGGER.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
logging.getLogger("botocore").setLevel(logging.ERROR)

SUCCESS = "SUCCESS"
FAILED = "FAILED"

http = urllib3.PoolManager()
FUNCTION_NAME = os.environ['AWS_LAMBDA_FUNCTION_NAME']


def send(event, context, responseStatus, responseData, physicalResourceId=FUNCTION_NAME, noEcho=False, reason=None):
    errors = [v for k, v in responseData.items() if 'ERROR' in k]
    if errors:
        reason = f'[CloudWatch Log Stream: {context.log_stream_name}] {errors}'

    responseUrl = event['ResponseURL']

    LOGGER.info(responseUrl)

    responseBody = {
        'Status': responseStatus,
        'Reason': reason or "See the details in CloudWatch Log Stream: {}".format(context.log_stream_name),
        'PhysicalResourceId': physicalResourceId or context.log_stream_name,
        'StackId': event['StackId'],
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'],
        'NoEcho': noEcho,
        'Data': responseData
    }

    json_responseBody = json.dumps(responseBody)

    LOGGER.info("Response body:")
    LOGGER.info(json_responseBody)

    headers = {
        'content-type': '',
        'content-length': str(len(json_responseBody))
    }

    try:
        response = http.request('PUT', responseUrl, headers=headers, body=json_responseBody)
        LOGGER.info(f"Status code: {response.status}")

    except Exception as e:
        LOGGER.error("send(..) failed executing http.request(..):", e)
