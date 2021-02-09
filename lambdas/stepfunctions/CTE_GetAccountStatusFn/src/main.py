# (c) 2021 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
# This AWS Content is provided subject to the terms of the AWS Customer Agreement
# available at http://aws.amazon.com/agreement or other written agreement between
# Customer and Amazon Web Services, Inc.

import json
import logging
import boto3
from helper import get_outputs_from_record

logging.basicConfig()
logger = logging.getLogger()
logging.getLogger("botocore").setLevel(logging.ERROR)
logger.setLevel(logging.INFO)


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

    sc_client = boto3.client('servicecatalog')

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
        logger.info(f"Account creation has not started for {payload['CustomResourceEvent']['AccountName']}")
        logger.info("Attempting to create the account, again...")
        return

    response = sc_client.describe_provisioned_product(
        Id=provision_product_id
    )
    logging.info(response)

    status = response['ProvisionedProductDetail']['Status']
    if status == 'AVAILABLE':
        outputs = get_outputs_from_record(
            rec_id=record_id,
            client=sc_client
        )
        payload['Account'] = {"Status": "SUCCESS", "Outputs": outputs}

    elif status in ('TAINTED', 'ERROR'):
        payload['Account'] = {"Status": "FAILED", "ERROR": response['ProvisionedProductDetail']['StatusMessage']}

    elif status == 'UNDER_CHANGE':
        payload['Account'] = {"Status": "UNDER_CHANGE"}

    return payload
