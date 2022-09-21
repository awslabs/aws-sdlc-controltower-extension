# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import os
import json
import logging
import cfnresponse

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOGGER = logging.getLogger()
LOGGER.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
logging.getLogger("botocore").setLevel(logging.ERROR)


def lambda_handler(event, context):
    """This function will get send a SUCCESS or a FAILED CloudFormation Response back to the orginial CloudFormation
    Custom Resource execution

    Args:
        event (dict): Event information passed in by the AWS Step Functions
        context (object): Lambda Function context information

    Returns:
        N/A
    """
    print(json.dumps(event))
    account = event["Payload"]['Account']

    if event["Payload"]['Account'].get("Outputs"):
        response_body = event["Payload"]['Account'].get("Outputs")
    elif event["Payload"]['Account'].get("ERROR"):
        response_body = event["Payload"]['Account']
    else:
        response_body = ""

    response_event = event["Payload"]['CustomResourceEvent']
    print(f"response_body:{response_body}")

    if account["Status"] == 'SUCCESS':
        cfn_res = cfnresponse.SUCCESS
    elif account["Status"] == 'FAILED':
        cfn_res = cfnresponse.FAILED

    cfnresponse.send(
        event=response_event,
        context=context,
        responseStatus=cfn_res,
        responseData=response_body
    )
