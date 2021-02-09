# (c) 2021 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
# This AWS Content is provided subject to the terms of the AWS Customer Agreement
# available at http://aws.amazon.com/agreement or other written agreement between
# Customer and Amazon Web Services, Inc.

import ast
import logging
import json
import cfnresponse
from sts_helper import assume_role_arn
from cfn_helper import create_update_stack, describe_stack, delete_stack, enable_termination_protection, \
    disable_termination_protection
from client_session_helper import boto3_session

logging.basicConfig()
logger = logging.getLogger()
logging.getLogger("botocore").setLevel(logging.ERROR)
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    print(json.dumps(event))
    response_data = dict()
    response = None
    description = ''
    config = event['ResourceProperties']['Parameters']['Configuration']
    base_stack_name = config['StackName']
    resources = config['Resources']
    outputs = dict()
    regions = list()
    count = 1

    # This will replace to all for local supported functions to ensure they will run as expected
    resources = ast.literal_eval(json.dumps(resources).replace("&Ref", "Ref").replace("&Fn", "Fn"))
    logger.debug(f"Resources Post Replace:{resources}")

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
        logger.debug(f"Outputs Post Replace:{outputs}")

    except Exception as e:
        logger.warning(e)
        logger.warning(f"No Outputs found from template {config['StackName']}")
        pass

    # Get the number of regions it will deploy to to allow for proper Cfn Outputs
    num_of_regions = len(regions)

    for region in regions:
        logger.info(f"Running in Region:{region}")
        config['StackName'] = base_stack_name.replace('%_REGION_%', region)
        _resources = json.loads(json.dumps(resources).replace("%_REGION_%", region))

        try:
            credentials = assume_role_arn(role_arn=config['RoleArn'])
            session = boto3_session(region=region, credentials=credentials)

        except Exception as e:
            logger.error(f"Assume Role Error:{e}", exc_info=True)
            response_data['ERROR'] = str(e)
            cfnresponse.send(event, context, cfnresponse.FAILED, response_data, "CustomResourcePhysicalID")
            return

        if event['RequestType'] == "Delete":
            try:
                if config.get("OnFailure", "DELETE") == "DELETE":
                    disable_termination_protection(stack_name=config['StackName'], session=session)
                    response = delete_stack(stack_name=config['StackName'], session=session)

                    if response:
                        response_data['Data'] = response

                cfnresponse.send(event, context, cfnresponse.SUCCESS, response_data, "CustomResourcePhysicalID")
                return

            except Exception as e:
                logger.error(f"Deleting Stack Error:{e}", exc_info=True)
                response_data['ERROR'] = str(e)
                cfnresponse.send(event, context, cfnresponse.FAILED, response_data, "CustomResourcePhysicalID")
                return

        else:
            try:
                logger.debug(f"Deployed Resources:{_resources}")
                template = {
                    "AWSTemplateFormatVersion": "2010-09-09",
                    "Description": "{}(Lambda:CrossAccountCloudFormation)".format(description),
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
                            logger.info('Not Stack Outputs Found')

                    except Exception as e:
                        logger.error(f"Error getting Stack Details:{e}", exc_info=True)
                        raise

                if config.get('TerminationProtection') and (config['TerminationProtection'].lower() == 'true'):
                    enable_termination_protection(stack_name=config['StackName'], session=session)

                logger.debug(f"response_data:{response_data}")
                cfnresponse.send(event, context, cfnresponse.SUCCESS, response_data, "CustomResourcePhysicalID")

            except Exception as e:
                logger.error(f"Main Function Error:{e}", exc_info=True)
                if response:
                    response_data['ERROR'] = f"{response} - {str(e)}"

                else:
                    response_data['ERROR'] = str(e)

                cfnresponse.send(event, context, cfnresponse.FAILED, response_data, "CustomResourcePhysicalID")

        count += 1
