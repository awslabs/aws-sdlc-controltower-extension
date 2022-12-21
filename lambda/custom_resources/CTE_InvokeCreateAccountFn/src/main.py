# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import os
import json
import logging
import cfnresponse
import boto3
from helper import generate_sf_exec_name

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOGGER = logging.getLogger()
LOGGER.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
logging.getLogger("botocore").setLevel(logging.ERROR)


def lambda_handler(event, context):
    """This function will initiate the AWS Step Function for building an AWS Account.

    Args:
        event (dict): Event information passed in by the CloudFormation from the Custom Resource
        context (object): Lambda Function context information

    Returns:
        N/A
    """
    print(json.dumps(event))
    response_body = {}
    exec_count = 0
    sfn_client = boto3.client('stepfunctions')
    resource_properties = event["ResourceProperties"]
    state_machine_arn = resource_properties["CreateAccountSfn"]
    sc_parameters = resource_properties['ServiceCatalogParameters']

    if event['RequestType'] == "Delete":
        cfnresponse.send(
            event=event,
            context=context,
            responseStatus=cfnresponse.SUCCESS,
            responseData=response_body
        )

    else:
        try:
            sf_exec_name = generate_sf_exec_name(
                account_name=sc_parameters['AccountName'],
                client=sfn_client,
                statemachine_arn=state_machine_arn
            )
            LOGGER.info(f"Invoking State Machine: {state_machine_arn} with input: {event}")

            while True:
                try:
                    # Start step function
                    sfn_client.start_execution(
                        stateMachineArn=state_machine_arn,
                        name=sf_exec_name,
                        input=json.dumps(event),
                    )
                    break

                except Exception as err:
                    logging.debug(err)
                    # If execution already exists increment count and try again
                    if "when calling the StartExecution operation: Execution Already Exists" in str(err):
                        exec_count = (exec_count + 1)
                        sf_exec_name = f"{sc_parameters['AccountName']}-{str(exec_count).zfill(2)}"
                        LOGGER.debug(f'Incrementing count and trying with execution name:{sf_exec_name}')

                    else:
                        raise Exception(err) from err

        except Exception as e:
            LOGGER.error(e, exc_info=True)
            response_body['ERROR'] = str(e)
            cfnresponse.send(
                event=event,
                context=context,
                responseStatus=cfnresponse.FAILED,
                responseData=response_body
            )
