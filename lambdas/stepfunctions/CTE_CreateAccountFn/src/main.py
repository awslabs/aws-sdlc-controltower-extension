# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import json
import logging
import os
import time
import random
import boto3
import cfnresponse
from helper import search_provisioned_products, build_service_catalog_parameters, create_provision_product, \
    get_provisioning_artifact_id

logging.basicConfig()
logger = logging.getLogger()
logging.getLogger("botocore").setLevel(logging.ERROR)
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """This function will create/setup account(s) that will live within a Control Tower ecosystem.

    Args:
        event (dict): Event information passed in by the AWS Step Functions
        context (object): Lambda Function context information

    Returns:
        dict: Payload values that will be passed to the next step in the Step Function
    """
    print(json.dumps(event))
    payload = dict()

    try:
        # If the Payload key is found this indicates that this isn't the first attempt that the
        #  CreateAccount Function has been executed.
        if event.get('Payload'):
            resource_prop = event['Payload']['CustomResourceEvent']['ResourceProperties']
            payload = event['Payload']

        else:
            resource_prop = event['ResourceProperties']
            payload['CustomResourceEvent'] = event

        # Look for account name in Service Catalog Provisioned Product list
        sc_client = boto3.client('servicecatalog')

        # Since cfn calls could occur in parallel adding a random sleep to help reduce multiple executions
        sleep_time = random.randrange(60)
        logger.info(f"Sleeping for {sleep_time} to help reduce duplicate executions")
        time.sleep(sleep_time)

        provisioned_product = search_provisioned_products(
            search_pp_name=resource_prop['ServiceCatalogParameters']['AccountName'],
            client=sc_client
        )

        # If not found, execute new SC Product Artifact deployment
        if not provisioned_product:
            product_name = os.environ['SC_CT_PRODUCT_NAME']
            sc_params = build_service_catalog_parameters(
                parameters=resource_prop['ServiceCatalogParameters']
            )
            pa_id = get_provisioning_artifact_id(
                product_name=product_name,
                client=sc_client
            )
            pp_info = create_provision_product(
                product_name=product_name,
                pp_name=resource_prop['ServiceCatalogParameters']['AccountName'],
                pa_id=pa_id,
                client=sc_client,
                params=sc_params
            )
            del pp_info['RecordDetail']['CreatedTime']
            del pp_info['RecordDetail']['UpdatedTime']
            payload['ServiceCatalogEvent'] = pp_info['RecordDetail']

        else:
            payload['ServiceCatalogEvent'] = provisioned_product

        logger.info(f"Payload:{payload}")
        return payload

    # If function fails return a FAILED signal to CFN
    except Exception as e:
        logger.error(e)
        response_body = dict()
        response_body['ERROR'] = str(e)
        cfnresponse.send(
            event=payload['CustomResourceEvent'],
            context=context,
            responseStatus=cfnresponse.FAILED,
            responseData=response_body
        )
