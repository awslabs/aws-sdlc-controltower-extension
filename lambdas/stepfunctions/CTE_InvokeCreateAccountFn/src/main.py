# (c) 2021 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
# This AWS Content is provided subject to the terms of the AWS Customer Agreement
# available at http://aws.amazon.com/agreement or other written agreement between
# Customer and Amazon Web Services, Inc.

import json
import cfnresponse
import logging
import boto3

logging.basicConfig()
logger = logging.getLogger()
logging.getLogger("botocore").setLevel(logging.ERROR)
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """This function will initiate the AWS Step Function for building an AWS Account.

    Args:
        event (dict): Event information passed in by the CloudFormation from the Custom Resource
        context (object): Lambda Function context information

    Returns:
        N/A
    """
    print(json.dumps(event))
    response_body = dict()
    sfn_client = boto3.client('stepfunctions')
    resource_properties = event["ResourceProperties"]
    state_machine_arn = resource_properties["CreateAccountSfn"]

    if event['RequestType'] == "Delete":
        cfnresponse.send(
            event=event,
            context=context,
            responseStatus=cfnresponse.SUCCESS,
            responseData=response_body,
            physicalResourceId="CustomResourcePhysicalID"
        )

    else:
        try:
            logger.info(f"Invoking State Machine: {state_machine_arn} with input: {event}")
            sfn_client.start_execution(
                stateMachineArn=state_machine_arn,
                input=json.dumps(event)
            )

        except Exception as e:
            logger.error(e, exc_info=True)
            response_body['ERROR'] = str(e)
            cfnresponse.send(
                event=event,
                context=context,
                responseStatus=cfnresponse.FAILED,
                responseData=response_body,
                physicalResourceId="CustomResourcePhysicalID"
            )
