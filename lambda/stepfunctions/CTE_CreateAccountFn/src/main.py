# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import json
import logging
import os
import time
import random
import boto3
from helper import search_provisioned_products, build_service_catalog_parameters, create_update_provision_product, \
    get_provisioning_artifact_id, get_ou_id
from custom_logger import CustomLogger

LOGGER = CustomLogger().logger
SC_CLIENT = boto3.client('servicecatalog')


def lambda_handler(event, context):
    """This function will create/setup account(s) that will live within a Control Tower ecosystem.

    Args:
        event (dict): Event information passed in by the AWS Step Functions
        context (object): Lambda Function context information

    Returns:
        dict: Payload values that will be passed to the next step in the Step Function
    """
    print(json.dumps(event))
    payload = {}
    update_needed = None

    try:
        # If the Payload key is found this indicates that this isn't the first attempt that the
        #  CreateAccount Function has been executed.
        if event.get('Payload'):
            resource_prop = event['Payload']['CustomResourceEvent']['ResourceProperties']
            payload = event['Payload']

        else:
            resource_prop = event['ResourceProperties']
            payload['CustomResourceEvent'] = event

        # See if there's a difference between new and old SC Parameters
        if event.get('OldResourceProperties'):
            logging.info("Found update call, identifying if Service Catalog needs to be updated")
            new = json.dumps(event['ResourceProperties']['ServiceCatalogParameters'])
            current = json.dumps(event['OldResourceProperties']['ServiceCatalogParameters'])
            update_needed = (new != current)

        # Since cfn calls could occur in parallel adding a random sleep to help reduce multiple executions
        sleep_time = random.randrange(60)
        LOGGER.info(f"Sleeping for {sleep_time} to help reduce duplicate executions")
        time.sleep(sleep_time)

        provisioned_product = search_provisioned_products(
            search_pp_name=resource_prop['ServiceCatalogParameters']['AccountName'],
            client=SC_CLIENT
        )

        # If not found, execute new SC Product Artifact deployment
        if not provisioned_product or update_needed:
            product_name = os.getenv('SC_CT_PRODUCT_NAME')
            ou_name = resource_prop['ServiceCatalogParameters']['ManagedOrganizationalUnit'].split(":")[-1]
            ou_id = get_ou_id(ou_path=resource_prop['ServiceCatalogParameters']['ManagedOrganizationalUnit'])
            resource_prop['ServiceCatalogParameters']['ManagedOrganizationalUnit'] = f"{ou_name} ({ou_id})"

            sc_params = build_service_catalog_parameters(
                parameters=resource_prop['ServiceCatalogParameters']
            )
            pa_id = get_provisioning_artifact_id(
                product_name=product_name,
                client=SC_CLIENT
            )

            pp_info = create_update_provision_product(
                product_name=product_name,
                pp_name=resource_prop['ServiceCatalogParameters']['AccountName'],
                pa_id=pa_id,
                client=SC_CLIENT,
                params=sc_params,
                update=update_needed,
            )
            del pp_info['RecordDetail']['CreatedTime']
            del pp_info['RecordDetail']['UpdatedTime']
            payload['ServiceCatalogEvent'] = pp_info['RecordDetail']

        else:
            payload['ServiceCatalogEvent'] = provisioned_product

        LOGGER.info(f"Payload:{payload}")
        return payload

    # If function fails return a FAILED signal to CFN
    except Exception as e:
        error_output = {
            "event": event,
            "status": "FAILED",
            "error": str(e)
        }
        LOGGER.error(e)
        raise TypeError(str(error_output)) from e
