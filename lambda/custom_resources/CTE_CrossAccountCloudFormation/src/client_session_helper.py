# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import os
import logging
import boto3
import botocore.exceptions as ex

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOGGER = logging.getLogger()
LOGGER.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
logging.getLogger("botocore").setLevel(logging.ERROR)


def boto3_session(region=None, credentials=None, profile=None):
    """Creates a boto3 session using optional profile

    Args:
        region (str, optional): AWS Region to create a boto3 session in
        credentials (str, optional): Name of the credential to use
        profile (str, optional): Name of the profile to use

    Returns:
        :obj:`boto3.session`: Returns a boto3 session object
    """
    args = {'region_name': region}
    try:
        if profile:
            args['profile_name'] = profile

        elif credentials:
            if 'AccessKeyId' in credentials.keys():
                args['aws_access_key_id'] = credentials['AccessKeyId']
                args['aws_secret_access_key'] = credentials['SecretAccessKey']
                args['aws_session_token'] = credentials['SessionToken']

            elif 'accessKeyId' in credentials.keys():
                args['aws_access_key_id'] = credentials['accessKeyId']
                args['aws_secret_access_key'] = credentials['secretAccessKey']
                args['aws_session_token'] = credentials['sessionToken']

        session = boto3.Session(**args)
        return session

    except BaseException as e:
        raise Exception(
            f"Failed to establish session to AWS: {str(e)}"
        ) from e


def boto3_client(service, assumed_credentials=None, session=None, region=None, profile=None):
    """Creates a boto3 client using the provided resource, credentials or profile

    Args:
        service (str): Name of the service to create a client with
        session (str, optional): AWS Session
        region (str, optional): AWS Region
        assumed_credentials (dict, optional): Assumed credentials dict returned from assume_role
        profile (str, optional): Name of the credential profile to use

    Returns:
        :obj:`boto3.client`: Returns a boto3 session object
    """
    args = {'service_name': service, 'region_name': region}

    if not session:
        session = boto3_session(profile)

    try:
        if assumed_credentials:
            if 'AccessKeyId' in assumed_credentials.keys():
                args['aws_access_key_id'] = assumed_credentials['AccessKeyId']
                args['aws_secret_access_key'] = assumed_credentials['SecretAccessKey']
                args['aws_session_token'] = assumed_credentials['SessionToken']

            elif 'accessKeyId' in assumed_credentials.keys():
                args['aws_access_key_id'] = assumed_credentials['accessKeyId']
                args['aws_secret_access_key'] = assumed_credentials['secretAccessKey']
                args['aws_session_token'] = assumed_credentials['sessionToken']

        client = session.client(**args)
        return client

    except BaseException as e:
        raise Exception(
            f"Failed to establish client with AWS: {str(e)}"
        ) from e
