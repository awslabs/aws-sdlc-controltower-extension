# (c) 2021 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
# This AWS Content is provided subject to the terms of the AWS Customer Agreement
# available at http://aws.amazon.com/agreement or other written agreement between
# Customer and Amazon Web Services, Inc.

import json
import logging
import cfnresponse

logging.basicConfig()
logger = logging.getLogger()
logging.getLogger("botocore").setLevel(logging.ERROR)
logger.setLevel(logging.INFO)


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
