# (c) 2021 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
# This AWS Content is provided subject to the terms of the AWS Customer Agreement
# available at http://aws.amazon.com/agreement or other written agreement between
# Customer and Amazon Web Services, Inc.

import logging
import boto3

logging.basicConfig()
logger = logging.getLogger()
logging.getLogger("botocore").setLevel(logging.ERROR)
logger.setLevel(logging.INFO)


def scan_provisioned_products(search_pp_name, client: boto3.client) -> dict:
    """Search for existing Service Catalog Provisioned Products

    Args:
        search_pp_name (str): Service Catalog Provisioned Product Name to search for
        client (boto3.client): Boto3 Client for Service Catalog

    Returns:
        str: Service Catalog Provisioned
    """
    logger.info('Making sure Control Tower is not already executing')
    paginator = client.get_paginator("scan_provisioned_products")
    for page in paginator.paginate(
            AccessLevelFilter={
                'Key': 'Account',
                'Value': 'self'
            }
    ):
        for x in page['ProvisionedProducts']:
            if x['Type'] == 'CONTROL_TOWER_ACCOUNT':

                # Since Control Tower has a serial method of deploying account this statement will check to see if
                #  there's and existing In-Progress deployment and will return provision the product name / status
                if x['Status'] == 'UNDER_CHANGE' and x['Name'] != search_pp_name:
                    logger.info(f"Found In-Progress Control Tower Deployment ({x['Name']})")
                    return {"ProvisionedProductName": x['Name'], "Status": x['Status']}

                # If existing provision product found return
                elif x['Name'] == search_pp_name:
                    logger.info(f"Found {x}")

                    # Removing Create time since it doesn't serializable JSON well
                    del x['CreatedTime']
                    return x


def search_provisioned_products(search_pp_name, client: boto3.client) -> dict:
    """Search for existing Service Catalog Provisioned Products. If it's not found
        then will search for any in-progress deployments since Control Tower has a
        serial method of deploying accounts.

    Args:
        search_pp_name (str): Service Catalog Provisioned Product Name to search for
        client (boto3.client): Boto3 Client for Service Catalog

    Returns:
        dict: Service Catalog Provisioned
    """
    logger.info(f"Searching for {search_pp_name}")
    response = client.search_provisioned_products(
        AccessLevelFilter={
            'Key': 'Account',
            'Value': 'self'
        },
        Filters={
            'SearchQuery': [f"name:{search_pp_name}"]
        }
    )
    if len(response['ProvisionedProducts']) > 0:
        provisioned_product = response['ProvisionedProducts'][0]
        logger.info(f"Found {provisioned_product}")

        # Removing Create time since it doesn't serializable JSON well
        del provisioned_product['CreatedTime']
        return provisioned_product
    else:
        # If the product has not been provisioned yet, Since Control Tower has a serial method of deploying
        # account this statement will check to see if there's and existing In-Progress deployment and will
        # return provision the product name / status
        logger.info(f"Did not find {search_pp_name}. Searching for any In-Progress Control Tower Deployments")
        return scan_provisioned_products(search_pp_name, client)


def build_service_catalog_parameters(parameters: dict) -> list:
    """Updates the format of the parameters to allow Service Catalog to consume them

    Args:
        parameters (dict): List of parameters in the format of
            {"key1":"value1", "key2":"value2"}

    Returns:
        list: Parameters in the format of {"Key":"string", "Value":"string"}
    """
    new_parameters = list()
    for key, value in parameters.items():
        y = dict()
        y['Key'] = key
        y['Value'] = value
        new_parameters.append(y)
    return new_parameters


def get_provisioning_artifact_id(product_name: str, client: boto3.client) -> str:
    """Retrieve the Default Service Catalog Provisioning Artifact Id from the Service Catalog Product specified in
    the definition call.

    Args:
        product_name (str): Service Catalog Product Name
        client (boto3.client): Boto3 Client for Service Catalog

    Returns:
        str: Service Catalog Provisioning Artifact Id
    """
    product_info = client.describe_product(
        Name=product_name
    )
    logger.info(product_info)

    for _product_info in product_info['ProvisioningArtifacts']:
        if _product_info['Guidance'] == 'DEFAULT':
            logger.info(f"Found ProvisioningArtifactId:{_product_info['Id']}")
            return _product_info['Id']


def create_provision_product(product_name: str, pp_name: str, pa_id: str, client: boto3.client, params=None, tags=None) -> dict:
    """Creates a Service Catalog Provisioned Product

    Args:
        product_name (str): Service Catalog Product Name
        pp_name (str): Service Catalog Provisioned Product Name
        pa_id (str): Service Catalog Provisioned Artifact Id
        client (boto3.client): Boto3 Client for Service Catalog
        params (list): List of Service Catalog Provisioned Product Parameters
        tags (list): List of tags to add to the Service Catalog Provisioned Product

    Returns:
        Return: boto3.client response for service catalog provision product
    """
    if params is None:
        params = []
    if tags is None:
        tags = []
    logging.info(f"Creating pp_id:{pp_name} with ProvisionArtifactId:{pa_id} in ProductName:{product_name}")
    logging.info(f"Parameters used:{params}")
    re = client.provision_product(
        ProductName=product_name,
        ProvisionedProductName=pp_name,
        ProvisioningArtifactId=pa_id,
        ProvisioningParameters=params,
        Tags=tags
    )
    logging.info(re)
    return re
