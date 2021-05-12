# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import os
import logging
from helper import retry_v2
from client_session_helper import boto3_client


logging.basicConfig()
logger = logging.getLogger()
logging.getLogger("botocore").setLevel(logging.ERROR)
logger.setLevel(logging.INFO)

function_name = os.environ['AWS_LAMBDA_FUNCTION_NAME']


@retry_v2(max_attempts=10, delay=30, error_code='AccessDenied')
def assume_role_arn(role_arn, role_session_name=function_name, profile=None):
    """Assumes the provided role name in the provided account number

    http://boto3.readthedocs.io/en/latest/reference/services/sts.html#STS.Client.assume_role

    Args:
        role_arn (str): Arn of the IAM Role to assume
        role_session_name (str, optional): The name you'd like to use for the session
            (suggested to use the lambda function name)
        profile (str, optional): Local AWS Profile name

    Returns:
        dict: Returns standard AWS dictionary with credential details
    """
    logger.info(f"Assuming Role:{role_arn}")
    sts_client = boto3_client(service='sts', profile=profile)

    assumed_role_object = sts_client.assume_role(
        RoleArn=role_arn,
        RoleSessionName=role_session_name
    )

    assumed_credentials = assumed_role_object['Credentials']
    return assumed_credentials
