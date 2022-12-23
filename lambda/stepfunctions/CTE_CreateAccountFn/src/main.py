# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import json
import logging
import os
import boto3
from helper import search_provisioned_products, build_service_catalog_parameters, create_update_provision_product, \
    get_provisioning_artifact_id, get_ou_id, scan_provisioned_products
from custom_logger import CustomLogger

LOGGER = CustomLogger().logger
SC_CLIENT = boto3.client('servicecatalog')


class OuNotFoundException(Exception):
    pass


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

        sc_parameters = resource_prop['ServiceCatalogParameters']

        # Update Account Information
        try:
            if "(" not in sc_parameters['ManagedOrganizationalUnit']:
                ou_name = sc_parameters['ManagedOrganizationalUnit'].split(":")[-1]
                ou_id = get_ou_id(ou_path=sc_parameters['ManagedOrganizationalUnit'])
                sc_parameters['ManagedOrganizationalUnit'] = f"{ou_name} ({ou_id})"
        except KeyError as key_error:
            raise OuNotFoundException(
                f'The organizational unit was not found. OU Name: {ou_name}') from key_error

        # Determine if there's already a Provisioned Product In-Progress
        pp_in_progress = scan_provisioned_products(
            search_pp_name=sc_parameters['AccountName'],
            client=SC_CLIENT
        )

        provisioned_product = search_provisioned_products(
            search_pp_name=sc_parameters['AccountName'],
            client=SC_CLIENT
        )

        # If not found, execute new SC Product Artifact deployment
        if (not pp_in_progress and not provisioned_product) or update_needed:
            product_name = os.getenv('SC_CT_PRODUCT_NAME')

            sc_params = build_service_catalog_parameters(
                parameters=sc_parameters
            )
            pa_id = get_provisioning_artifact_id(
                product_name=product_name,
                client=SC_CLIENT
            )

            pp_info = create_update_provision_product(
                product_name=product_name,
                pp_name=sc_parameters['AccountName'],
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
