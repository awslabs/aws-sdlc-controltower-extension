# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import os
import ast
import logging
import json
import cfnresponse
from sts_helper import assume_role_arn
from cfn_helper import create_update_stack, describe_stack, delete_stack, enable_termination_protection, \
    disable_termination_protection
from client_session_helper import boto3_session

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOGGER = logging.getLogger()
LOGGER.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
logging.getLogger("botocore").setLevel(logging.ERROR)


def lambda_handler(event, context):
    print(json.dumps(event))
    response_data = {}
    response = None
    description = ''
    config = event['ResourceProperties']['Parameters']['Configuration']
    base_stack_name = config['StackName']
    resources = config['Resources']
    outputs = {}
    regions = []
    count = 1

    # This will replace to all for local supported functions to ensure they will run as expected
    resources = ast.literal_eval(json.dumps(resources).replace("&Ref", "Ref").replace("&Fn", "Fn"))
    LOGGER.debug(f"Resources Post Replace:{resources}")

    # Get tags from Cfn Configuration
    tags = config.get('Tags')

    # If regions are specified within the Cfn Configuration use that list, if non are provided use
    #  the region that executed the cfn stack
    if config.get('Regions'):
        regions = config['Regions']

    else:
        regions.append(event['ResponseURL'].split("%3A")[3])

    if config.get('Description'):
        description = config['Description'] + ' '

    # This will replace to all for local supported functions to ensure they will run as expected
    try:
        outputs = config.get('Outputs', {})
        outputs = ast.literal_eval(json.dumps(outputs).replace("&Ref", "Ref").replace("&Fn", "Fn"))
        LOGGER.debug(f"Outputs Post Replace:{outputs}")

    except Exception as e:
        LOGGER.warning(e)
        LOGGER.warning(f"No Outputs found from template {config['StackName']}")

    # Get the number of regions it will deploy to allow for proper Cfn Outputs
    num_of_regions = len(regions)

    for region in regions:
        LOGGER.info(f"Running in Region:{region}")
        config['StackName'] = base_stack_name.replace('%_REGION_%', region)
        _resources = json.loads(json.dumps(resources).replace("%_REGION_%", region))

        try:
            credentials = assume_role_arn(role_arn=config['RoleArn'])
            session = boto3_session(region=region, credentials=credentials)

        except Exception as e:
            LOGGER.error(f"Assume Role Error:{e}", exc_info=True)
            response_data['ERROR'] = str(e)
            cfnresponse.send(
                event=event,
                context=context,
                responseStatus=cfnresponse.FAILED,
                responseData=response_data
            )
            return

        if event['RequestType'] == "Delete":
            try:
                if config.get("OnFailure", "DELETE") == "DELETE":
                    disable_termination_protection(stack_name=config['StackName'], session=session)
                    response = delete_stack(stack_name=config['StackName'], session=session)

                    if response:
                        response_data['Data'] = response

                cfnresponse.send(
                    event=event,
                    context=context,
                    responseStatus=cfnresponse.SUCCESS,
                    responseData=response_data
                )
                return

            except Exception as e:
                LOGGER.error(f"Deleting Stack Error:{e}", exc_info=True)
                response_data['ERROR'] = str(e)
                cfnresponse.send(
                    event=event,
                    context=context,
                    responseStatus=cfnresponse.FAILED,
                    responseData=response_data
                )
                return

        else:
            try:
                LOGGER.debug(f"Deployed Resources:{_resources}")
                template = {
                    "AWSTemplateFormatVersion": "2010-09-09",
                    "Description": f"{description}(Lambda:CrossAccountCloudFormation)",
                    "Resources": _resources,
                    "Outputs": outputs
                }

                response = create_update_stack(
                    stack_name=config['StackName'],
                    template=template,
                    cfn_params=None,
                    capability=config['Capabilities'],
                    waiter=True,
                    tags=tags,
                    session=session
                )

                if response:
                    response_data['Data'] = response
                    try:
                        stack_info = describe_stack(stack_name=config['StackName'], session=session)
                        if stack_info["Stacks"][0].get("Outputs"):
                            for output in stack_info["Stacks"][0]["Outputs"]:
                                if num_of_regions > 1:
                                    response_data[output["OutputKey"] + f"_Region{count}"] = output["OutputValue"]
                                else:
                                    response_data[output["OutputKey"]] = output["OutputValue"]
                        else:
                            LOGGER.info('Not Stack Outputs Found')

                    except Exception as e:
                        LOGGER.error(f"Error getting Stack Details:{e}", exc_info=True)
                        raise

                if config.get('TerminationProtection') and (config['TerminationProtection'].lower() == 'true'):
                    enable_termination_protection(stack_name=config['StackName'], session=session)

                LOGGER.debug(f"response_data:{response_data}")
                cfnresponse.send(
                    event=event,
                    context=context,
                    responseStatus=cfnresponse.SUCCESS,
                    responseData=response_data
                )

            except Exception as e:
                LOGGER.error(f"Main Function Error:{e}", exc_info=True)
                if response:
                    response_data['ERROR'] = f"{response} - {str(e)}"

                else:
                    response_data['ERROR'] = str(e)

                cfnresponse.send(
                    event=event,
                    context=context,
                    responseStatus=cfnresponse.FAILED,
                    responseData=response_data
                )
        count += 1
