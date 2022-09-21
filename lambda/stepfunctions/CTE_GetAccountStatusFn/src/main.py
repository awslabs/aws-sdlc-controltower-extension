# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import os
import json
import logging
import boto3
from helper import get_outputs_from_record

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOGGER = logging.getLogger()
LOGGER.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
logging.getLogger("botocore").setLevel(logging.ERROR)

SC_CLIENT = boto3.client('servicecatalog')


def lambda_handler(event, context):
    """This function will get the AWS Service Catalog / Control Tower Account Deployment status.

    Args:
        event (dict): Event information passed in by the AWS Step Functions
        context (object): Lambda Function context information

    Returns:
        dict: Payload with additional values for Account Status. This will be passed to the next step in the
        Step Function.
    """
    print(json.dumps(event))
    payload = event['Payload']

    try:
        # If existing provisioned product
        if payload['ServiceCatalogEvent'].get('Id'):
            provision_product_id = payload['ServiceCatalogEvent']['Id']
            record_id = payload['ServiceCatalogEvent']['LastProvisioningRecordId']

        # If creating a new provisioned product
        elif payload['ServiceCatalogEvent'].get('ProvisionedProductId'):
            provision_product_id = payload['ServiceCatalogEvent']['ProvisionedProductId']
            record_id = payload['ServiceCatalogEvent']['RecordId']

        # Account Creation hasn't started
        else:
            LOGGER.info(f"Account creation has not started for {payload['CustomResourceEvent']['AccountName']}")
            LOGGER.info("Attempting to create the account, again...")
            return

        response = SC_CLIENT.describe_provisioned_product(
            Id=provision_product_id
        )
        logging.info(response)

        status = response['ProvisionedProductDetail']['Status']
        if status == 'AVAILABLE':
            outputs = get_outputs_from_record(
                rec_id=record_id,
                client=SC_CLIENT
            )
            payload['Account'] = {"Status": "SUCCESS", "Outputs": outputs}

        elif status in ('TAINTED', 'ERROR'):
            payload['Account'] = {"Status": "FAILED", "ERROR": response['ProvisionedProductDetail']['StatusMessage']}

        elif status == 'UNDER_CHANGE':
            payload['Account'] = {"Status": "UNDER_CHANGE"}

        return payload

    except Exception as e:
        error_output = {
            "event": event['Payload']['CustomResourceEvent'],
            "status": "FAILED",
            "error": str(e)
        }
        LOGGER.error(e)
        raise TypeError(str(error_output)) from e
