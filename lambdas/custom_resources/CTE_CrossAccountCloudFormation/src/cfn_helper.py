# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import re
import json
import time
import logging
from datetime import datetime, timezone
import botocore.exceptions as ex
from client_session_helper import boto3_client
from helper import retry_v2
from cfn_tools import load_yaml

logging.basicConfig()
logger = logging.getLogger()
logging.getLogger("botocore").setLevel(logging.ERROR)
logger.setLevel(logging.INFO)


def create_update_stack(stack_name, template, cfn_params, capability, region='us-east-1', waiter=False, tags=None, session=None):
    """Creates or updates a cloudformation stack using the provided parameters and
    optionally waits for it to be complete

    Args:
        stack_name (str): Name of the stack to create/update
        template (str or dict): Path to the template file on disk to create stack with
        cfn_params (list of dict, optional): List of parameter structures that specify input parameters for the stack
        capability (str): The capability string noting if the stack contains IAM or custom named IAM resources
                            Options: 'CAPABILITY_IAM'|'CAPABILITY_NAMED_IAM'
        region (str): AWS Region
        waiter (bool): True/False if we should wait for the stack to complete or immediately return response
        tags (list): tags set on CloudFormation stack
        session (object, optional): boto3 session object

    Returns:
        dict: Standard AWS response dict
    """
    # Setup default arguments for cfn
    args = dict()
    args['StackName'] = stack_name
    args['Capabilities'] = list()
    args['session'] = session

    # Setup CloudFormation Path and/or Body
    args['TemplateBody'] = json.dumps(template)
    template_body = args['TemplateBody']

    # Does CloudFormation Stack already Exists
    stack_exists = describe_stack(
        stack_name=stack_name,
        session=session
    )

    # Setup Tags
    if tags:
        args['Tags'] = tags
    if not tags and stack_exists:
        args['Tags'] = stack_exists['Stacks'][0]['Tags']

    # If CloudFormation stack is currently in progress pickup where it was left off
    in_progress_status = [
        "CREATE_IN_PROGRESS",
        "UPDATE_IN_PROGRESS",
        "DELETE_IN_PROGRESS",
        "ROLLBACK_IN_PROGRESS",
        "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS",
        "UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS",
        "UPDATE_ROLLBACK_IN_PROGRESS"
    ]

    if stack_exists and (stack_exists['Stacks'][0]['StackStatus'] in in_progress_status):
        wait_all_stacks([{"Name": stack_name, "Session": session}])
        return

    # Setup capability to be a list so CloudFormation doesn't fail
    if isinstance(capability, str):
        args['Capabilities'] = [capability]
    elif isinstance(capability, list):
        args['Capabilities'] = capability

    # Check to see if an Update or Create needs to occur
    if stack_exists:
        # if stack exists get integration existing / override parameters
        if stack_exists['Stacks'][0].get('Parameters'):
            logger.info(f"Parameters found in existing Cfn Stack ({stack_name})")
            parameters = update_parameters(
                override_parameters=cfn_params,
                current_parameters=stack_exists['Stacks'][0]['Parameters']
            )

        else:
            logger.info(f"No Parameters found in existing Cfn Stack ({stack_name})")
            parameters = update_parameters(override_parameters=cfn_params)

        args['Parameters'] = remove_unused_parameters(template=template_body, parameters=parameters)
        response = update_stack(**args)
        cfn_action = 'stack_update_complete'

    else:
        args['Parameters'] = update_parameters(override_parameters=cfn_params)
        logger.info(f"Parameters:{args['Parameters']}")
        response = create_stack(**args)
        cfn_action = 'stack_create_complete'

    # Check to see if a waiter is needed and a proper response was received
    if response and waiter:
        stack_id = response['StackId']
        stack_url = f"https://console.aws.amazon.com/cloudformation/home?region={region}#/stack/detail?stackId={re.sub('/', '%2F', stack_id)}"
        logger.info("Waiting for CloudFormation Stack to complete")
        wait_for_stack_complete(stack_name=stack_name, stack_url=stack_url, cfn_action=cfn_action, session=session)

    return response


def update_parameters(override_parameters=None, current_parameters=None):
    """This will diff 2 sets of CloudFormation Parameters and will set any duplicate ones to
    the Override value

    Args:
        override_parameters (dict or list, optional): Override Parameters to deploy a CloudFormation Template
        current_parameters (list, optional): Path to the template file on disk to create stack with

    Returns:
        list: A list of CloudFormation Parameters
    """
    # Parameters with override values
    parameters = list()
    logger.info(f"Override Parameters:{override_parameters}")
    logger.info(f"Current Parameters:{current_parameters}")

    if current_parameters:
        for c_param in current_parameters:
            parameters.append({"ParameterKey": c_param['ParameterKey'], "ParameterValue": c_param['ParameterValue']})

    if override_parameters and isinstance(override_parameters, dict):
        if override_parameters.get('Parameters'):
            logger.info('Found "Parameters" section in dict, using that value for all parameters.')
            override_parameters = override_parameters['Parameters']

        for key, value in override_parameters.items():
            # Parse through list to see if it needs to be updated.
            for parameter in parameters:
                if key == parameter['ParameterKey'] and value != parameter['ParameterValue']:
                    logger.info(f'Removing {{"ParameterKey": {key}, "ParameterValue": {parameter["ParameterValue"]} }}')
                    parameters.remove({"ParameterKey": key, "ParameterValue": parameter["ParameterValue"]})

            logger.info(f'Adding {{"ParameterKey": {str(key)}, "ParameterValue": {str(value)}}})')
            temp = {"ParameterKey": str(key), "ParameterValue": str(value)}
            parameters.append(temp)

    elif override_parameters and isinstance(override_parameters, list):
        if not current_parameters:
            parameters = override_parameters
        else:
            for o_param in override_parameters:
                # Parse through list to see if it needs to be updated.
                for c_param in parameters:
                    if o_param['ParameterKey'] == c_param['ParameterKey'] and \
                            o_param['ParameterValue'] != c_param['ParameterValue']:
                        logger.info(
                            f"Replacing Parameter:{o_param['ParameterKey']} with Value:{o_param['ParameterValue']}")
                        parameters.remove(
                            {"ParameterKey": c_param['ParameterKey'], "ParameterValue": c_param['ParameterValue']})
                        parameters.append(
                            {"ParameterKey": o_param['ParameterKey'], "ParameterValue": o_param['ParameterValue']})

    logger.info(f"New Deployment Parameters:{parameters}")
    return parameters


def remove_unused_parameters(template, parameters):
    """This will scan each parameter to ensure it still exists in the
    AWS CloudFormation template

    Args:
        template (str): String of AWS CloudFormation Template
        parameters (list): List of AWS CloudFormation Parameters

    Returns:
        str: Returns the StackStatus message from the response
    """
    return_parameters = list()
    logger.info(f"Scanning Parameters to be removed - {parameters}")
    logger.debug(f"template:{template}")
    cfn_template = load_yaml(template)
    template_params = cfn_template.get('Parameters')
    if template_params:
        logger.info(f"Template Parameters:{template_params}")
        template_parameters_keys = template_params.keys()

        for parameter in parameters:
            logger.debug(f"Checking Parameter:{parameter} against template_parameters_keys:{template_parameters_keys}")
            param_value = parameter['ParameterKey']
            if param_value in template_parameters_keys:
                logger.info(f"Found Parameter:{param_value} in template, appending to return parameter list")
                return_parameters.append(parameter)

            else:
                logger.info(f"Parameter:{param_value} was not found in template")

    return return_parameters


def get_stack_status(stack_name, session=None):
    """Gets the status of a CloudFormation stack

    Args:
        stack_name (str): Name of the stack to get the status of
        session (object, optional): boto3 session object

    Returns:
        str: Returns the StackStatus message from the response
    """
    logger.debug(f"Checking CloudFormation Status of {stack_name}")
    response = describe_stack(stack_name=stack_name, session=session)
    logger.debug(f"Describe Stack Response:{response}")
    return response['Stacks'][0]['StackStatus']


def wait_all_stacks(stack_list):
    """Loops through all stacks in list checking status, raises Exception if any failed

    Args:
        stack_list (list of dict): List of dicts with 'Name' and 'AccountNumber' per stack to wait on

    Returns:
        None
    """
    successful_cfn_list = [
        'CREATE_COMPLETE',
        'UPDATE_COMPLETE'
    ]
    failure_cfn_list = [
        'CREATE_FAILED',
        'DELETE_FAILED',
        'ROLLBACK_COMPLETE',
        'UPDATE_ROLLBACK_COMPLETE',
        'UPDATE_ROLLBACK_FAILED',
        'ROLLBACK_FAILED'
    ]
    duration = 30
    timeout = 1
    failed_list = list()

    # Stack_list [{"StackName": name, "AssumedCredentials": creds}]
    while stack_list and duration > timeout:
        for stack in stack_list:
            remove_stack_list = False
            stack_status = get_stack_status(stack_name=stack['Name'], session=stack['Session'])
            logger.info(f"Stack ({stack['Name']}) Status:{stack_status}")
            if stack_status in successful_cfn_list:
                logger.info(f"{stack['Name']} was successful, removing from Status list")
                remove_stack_list = True

            elif stack_status in failure_cfn_list:
                logger.info(f"{stack['Name']} was failed, removing from Status list and getting more information")
                failure = determine_stack_failure_event(stack_name=stack['Name'], session=stack['Session'])
                failed_list.append({"Name": stack['Name'], "Failure": failure})
                remove_stack_list = True

            if remove_stack_list:
                try:
                    stack_list.remove(stack)
                except ValueError:
                    logger.warning(f"Stack {stack} not in list:{stack_list}")

        timeout += 1
        time.sleep(10)

    if failed_list:
        raise Exception(failed_list)


def get_stack_output_parameter(stack_name, output_name, session=None):
    """Gets the value of the provided output from a stack

    Args:
        stack_name (str): Name of the stack to check
        output_name (str): Name of the CFN output to get the value of
        session (object, optional): boto3 session object

    Returns:
        str: Value of the output
    """
    response = describe_stack(stack_name, session=session)
    for x in response['Stacks'][0]['Outputs']:
        if x['OutputKey'] == output_name:
            return x['OutputValue']


def get_stack_output_parameters(stack_name, session=None):
    """Gets the value of all outputs of the provided stack

    Args:
        stack_name (str): Name of the stack to check
        session (object, optional): boto3 session object

    Returns:
        dict: Returns a dict with all of the OutputKeys and Values
    """
    output_values = dict()
    response = describe_stack(stack_name=stack_name, session=session)
    if response['Stacks'][0].get('Outputs'):
        for x in response['Stacks'][0]['Outputs']:
            output_values[x['OutputKey']] = x['OutputValue']

        return output_values


def determine_stack_failure_event(stack_name, session=None):
    """Gets the ResourceStatusReason of the provided stack name and prints it

    Args:
        stack_name (str): Name of the stack to check
        session (object, optional): boto3 session object

    Returns:
        None
    """
    err_msg = None
    cfn_failure_list = [
        'CREATE_FAILED',
        'ROLLBACK_COMPLETE',
        'ROLLBACK_FAILED',
        'UPDATE_FAILED',
        'UPDATE_ROLLBACK_COMPLETE',
        'UPDATE_ROLLBACK_FAILED',
        'UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS'
    ]

    response = describe_stack_events(stack_name=stack_name, session=session)
    # logger.info(f"StackEvents:{response['StackEvents']}")
    for x in response['StackEvents']:
        if x['ResourceStatus'] in cfn_failure_list:
            # logger.info(f"Found stack ResourceStatus in failure list")
            if x.get('ResourceStatusReason'):
                err_msg = f"{x['LogicalResourceId']} - {x['ResourceStatusReason']}"
                logger.info(
                    f"Stack:{stack_name} - Error:{x['ResourceStatusReason']} LogicalResourceId:{x['LogicalResourceId']}"
                )

    return err_msg


def wait_for_stack_complete(stack_name, stack_url, cfn_action, session=None):
    """Waits for the provided stack to finish being created

    Args:
        stack_name (str): Name of the stack to wait on
        stack_url (str): Url for the AWS CloudFormation Stack
        cfn_action (str):  "stack_update_complete" or "stack_create_complete"
        session (object, optional): boto3 session object

    Returns:
        None
    """

    try:
        waiter = get_stack_waiter(event=cfn_action, session=session)
        waiter.wait(StackName=stack_name)

    except ex.WaiterError as e:
        logger.error(f"WaiterError: {e}")
        response = determine_stack_failure_event(stack_name=stack_name, session=session)
        raise Exception(f"Stack Failure: {stack_url} [ERROR] {response}")


def wait_for_stack_delete_complete(stack_name, session=None):
    """Waits for the provided stack to finish being deleted

    Args:
        stack_name (str): Name of the stack to wait on
        session (object, optional): boto3 session object

    Returns:
        None
    """

    try:
        waiter = get_stack_waiter(event='stack_delete_complete', session=session)
        waiter.wait(StackName=stack_name)

    except ex.WaiterError as e:
        logger.error(f"WaiterError in wait_for_stack_delete_complete: {e}")
        response = determine_stack_failure_event(stack_name=stack_name, session=session)
        raise Exception(f"Stack Failure: {stack_name} [ERROR] {response}")


def describe_stack(stack_name, session=None):
    """Performs describe_stack on the provided stack name

    http://boto3.readthedocs.io/en/latest/reference/services/cloudformation.html#CloudFormation.Client.describe_stacks

    Args:
        stack_name (str): Name of the stack to describe
        session (object, optional): boto3 session object

    Returns:
        dict: Standard AWS dictionary with stack details
    """
    client = boto3_client(service='cloudformation', session=session)
    try:
        logger.info(f"Getting details about CloudFormation Stack:{stack_name}")
        response = client.describe_stacks(StackName=stack_name)
        return response

    except ex.ClientError as e:
        if str(e).endswith(" does not exist"):
            logger.warning(f"Stack, {stack_name} does not exist...")
            # return False

        else:
            raise ex.ClientError(
                f"Failed to lookup stack {stack_name}: {str(e)}"
            )

    except Exception as e:
        logger.warning(f"describe_stack error:{str(e)}")


def describe_stack_events(stack_name, session=None):
    """Performs describe_stack_events on the provided stack name

    http://boto3.readthedocs.io/en/latest/reference/services/cloudformation.html#CloudFormation.Client.describe_stack_events

    Args:
        stack_name (str): Name of the stack to describe
        session (object, optional): boto3 session object

    Returns:
        dict: Standard AWS dictionary with stack event details
    """
    client = boto3_client(service='cloudformation', session=session)
    try:
        response = client.describe_stack_events(StackName=stack_name)
        return response

    except ex.ClientError as e:
        if str(e).endswith(" does not exist"):
            raise ex.NotFoundException(
                f"Could not find stack with name {stack_name}"
            )

        else:
            raise ex.ClientError(
                f"Failed to lookup stack events for {stack_name}: {str(e)}"
            )


def validate_template(template, session=None):
    """Performs template validation on the provided template body.

    http://boto3.readthedocs.io/en/latest/reference/services/cloudformation.html#CloudFormation.Client.validate_template

    Args:
        template (str): Body of a CFN template file, should already have been read in using helper.load_file(file)
        session (object, optional): boto3 session object

    Returns:
        dict: Standard AWS dictionary with validation results, raises exception if template is invalid
    """
    logger.info("Validating CloudFormation Template")
    client = boto3_client(service='cloudformation', session=session)
    try:
        response = client.validate_template(TemplateBody=template)
        return response

    except ex.ClientError as e:
        raise ex.ClientError(
            f"CloudFormation template validation failed: {str(e)}"
        )


@retry_v2(max_attempts=10, delay=30, error_message='Unable to fetch parameters')
def create_stack(**kwargs):
    """Creates a cloudformation stack using the provided parameters

    http://boto3.readthedocs.io/en/latest/reference/services/cloudformation.html#CloudFormation.Client.create_stack

    Args:
        stack_name (str): Name of the stack to create
        template (str): Body of a CFN template file, should already have been read in using general_helper.load_file(file)
        capability (str): The capability string noting if the stack contains IAM or custom named IAM resources
                            Options: 'CAPABILITY_IAM'|'CAPABILITY_NAMED_IAM'
        params (list of dict, optional): List of parameter structures that specify input parameters for the stack
        tags (list): tags set on cloudformation stack
        session (object, optional): boto3 session object

    Returns:
        dict: Standard AWS dictionary with create_stack results
    """
    logger.info(f"Arguments:{kwargs}")
    logger.info(f"Creating Stack:{kwargs['StackName']}")
    client = boto3_client(service='cloudformation', session=kwargs['session'])
    del kwargs['session']
    response = client.create_stack(**kwargs)

    return response


def delete_stack(stack_name:str, session=None):
    """Deletes the provided stack name

    http://boto3.readthedocs.io/en/latest/reference/services/cloudformation.html#CloudFormation.Client.delete_stack

    Args:
        stack_name (str): Name of the stack to delete
        session (object, optional): boto3 session object

    Returns:
        dict: Standard AWS dictionary with stack deletion results
    """
    client = boto3_client(service='cloudformation', session=session)
    response = client.delete_stack(
        StackName=stack_name
    )
    return response


@retry_v2(max_attempts=10, delay=30, error_message='Unable to fetch parameters')
def update_stack(**kwargs):
    """Updates an existing stack with new template

    http://boto3.readthedocs.io/en/latest/reference/services/cloudformation.html#CloudFormation.Client.update_stack

    Args:
        stack_name (str): Name of the stack to update
        template (str): Body of a CFN template file, should already have been read in using general_helper.load_file(file)
        capability (str): The capability string noting if the stack contains IAM or custom named IAM resources
                            Options: 'CAPABILITY_IAM'|'CAPABILITY_NAMED_IAM'
        params (list of dict, optional): List of parameter structures that specify input parameters for the stack
        tags (list): tags set on cloudformation stack
        session (object, optional): boto3 session object

    Returns:
        dict: Standard AWS dictionary with stack update results
    """
    logger.info(f"Arguments:{kwargs}")
    logger.info(f"Updating Stack:{kwargs['StackName']}")
    client = boto3_client(service='cloudformation', session=kwargs['session'])
    del kwargs['session']
    try:
        response = client.update_stack(**kwargs)

    except Exception as e:
        logger.warning(e)
        if re.search(r'(No updates are to be performed)', str(e)):
            logger.warning("No updates need to be performed...")
            response = False
        else:
            raise e

    return response


def get_stack_waiter(event, session=None):
    """Gets an object that can wait for some stack condition to be true

    http://boto3.readthedocs.io/en/latest/reference/services/cloudformation.html#CloudFormation.Client.get_waiter

    Args:
        event (str): Name of the event to wait for IE: 'stack_create_complete'
        session (object, optional): boto3 session object

    Returns:
        :obj:`boto3.waiter.Waiter`: Waiter object
    """

    client = boto3_client(service='cloudformation', session=session)
    try:
        waiter = client.get_waiter(event)

    except BaseException as e:
        raise ex.StackWaiterException(
            f"Failed to retrieve stack waiter for event {event}: {str(e)}"
        )

    return waiter


def list_stacks(session=None):
    """Gets a list of all CloudFormation stacks in the account

    http://boto3.readthedocs.io/en/latest/reference/services/cloudformation.html#CloudFormation.Client.list_stacks

    Args:
        session (object, optional): boto3 session object

    Returns:
        list of str: List of stack names in the account
    """
    stacks = []
    client = boto3_client(service='cloudformation', session=session)
    try:
        paginator = client.get_paginator("list_stacks")
        for page in paginator.paginate(
                StackStatusFilter=[
                    'CREATE_IN_PROGRESS',
                    'CREATE_FAILED',
                    'CREATE_COMPLETE',
                    'ROLLBACK_IN_PROGRESS',
                    'ROLLBACK_FAILED',
                    'ROLLBACK_COMPLETE',
                    'DELETE_IN_PROGRESS',
                    'DELETE_FAILED',
                    'UPDATE_IN_PROGRESS',
                    'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS',
                    'UPDATE_COMPLETE',
                    'UPDATE_ROLLBACK_IN_PROGRESS',
                    'UPDATE_ROLLBACK_FAILED',
                    'UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS',
                    'UPDATE_ROLLBACK_COMPLETE',
                    'REVIEW_IN_PROGRESS'
                ]
        ):
            for x in page['StackSummaries']:
                stacks.append(x['StackName'])

    except Exception as e:
        raise ex.CloudFormationException(
            f"Failed to get list of cloudformation templates: {str(e)}"
        )

    return stacks


def enable_termination_protection(stack_name, session=None):
    """Enables Termination Protection on CloudFormation Stacks

    Args:
        stack_name (str): Passing key word arguments that will be used to create the
        session (object, optional): boto3 session object

    Returns:
        none
    """
    logger.info(f"Setting Termination Protection on {stack_name}")
    try:
        client = boto3_client(service='cloudformation', session=session)
        response = client.update_termination_protection(
            EnableTerminationProtection=True,
            StackName=stack_name
        )
        logger.debug(response)

    except Exception as e:
        logger.error(str(e))
        raise Exception


def disable_termination_protection(stack_name, session=None):
    """Disables Termination Protection on CloudFormation Stacks

    Args:
        stack_name (str): Passing key word arguments that will be used to create the
        session (object, optional): boto3 session object

    Returns:
        none
    """
    try:
        client = boto3_client(service='cloudformation', session=session)
        stack_exists = describe_stack(stack_name=stack_name, session=session)
        if stack_exists:
            logger.info("Checking time difference between Stack Creation and now. (disable if < 20 min)")
            diff = datetime.now(timezone.utc) - stack_exists['Stacks'][0]['CreationTime']
            if stack_exists and (divmod(diff.days * 86400 + diff.seconds, 60)[0] < 20):
                logger.info(f"Disabling Termination Protection on {stack_name}")
                response = client.update_termination_protection(
                    EnableTerminationProtection=False,
                    StackName=stack_name
                )
                logger.debug(response)

            else:
                logger.warning('Time difference is greater than 20 min')

    except Exception as e:
        logger.error(str(e))
        raise Exception
