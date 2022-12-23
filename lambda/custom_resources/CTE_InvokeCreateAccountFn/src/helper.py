# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import os
import logging
import boto3

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOGGER = logging.getLogger()
LOGGER.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
logging.getLogger("botocore").setLevel(logging.ERROR)


def generate_sf_exec_name(account_name: str, client: boto3.client, statemachine_arn: str) -> str:
    """ Generates a Step Function execution name, based on the number of previous execution

    Args:
        account_name (str): The name in which the requester would like the account
        client (boto3.client): boto3 client for Step Function
        statemachine_arn (str): AWS Statemachine ARN

    Returns:
        str: Returns generated Step Function execution name
    """
    # Get number of executions with that account name in execution name
    count = 0

    paginator = client.get_paginator("list_executions")
    for page in paginator.paginate(stateMachineArn=statemachine_arn):
        for ex in page['executions']:
            if account_name in ex['name']:
                count = (count + 1)

    # If count is above 0 then append execution name with the next digit
    if count > 0:
        name = f"{account_name}-{str(count).zfill(2)}"
    else:
        name = account_name

    return name
