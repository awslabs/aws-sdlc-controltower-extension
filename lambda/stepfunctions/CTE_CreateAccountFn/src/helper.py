# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import time
import copy
import boto3
from custom_logger import CustomLogger

LOGGER = CustomLogger().logger


def scan_provisioned_products(search_pp_name, client: boto3.client, acc_fac_limit=5) -> dict:
    """Search for existing Service Catalog Provisioned Products

    Args:
        search_pp_name (str): Service Catalog Provisioned Product Name to search for
        client (boto3.client): Boto3 Client for Service Catalog
        acc_fac_limit (int):

    Returns:
        str: Service Catalog Provisioned
    """
    action_count = 0
    action_list = []
    LOGGER.info(f"Making sure ControlTower has not surpassed the number of concurrent actions (Limit:{acc_fac_limit}).")
    paginator = client.get_paginator("scan_provisioned_products")
    for page in paginator.paginate(
            AccessLevelFilter={
                'Key': 'Account',
                'Value': 'self'
            }
    ):
        for x in page['ProvisionedProducts']:
            if x['Type'] == 'CONTROL_TOWER_ACCOUNT':
                # Control Tower has a soft limit of 5 concurrent actions
                if x['Status'] == 'UNDER_CHANGE' and x['Name'] != search_pp_name:
                    action_count = (action_count + 1)
                    action_list.append(x['Name'])

    if action_count >= acc_fac_limit:
        LOGGER.info(f"Found more than {acc_fac_limit} In-Progress Control Tower Deployments)")
        return action_list


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
    LOGGER.info("Searching for %s", str(search_pp_name))
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
        LOGGER.info(f"Found {provisioned_product}")

        # Removing Create time since it doesn't serializable JSON well
        del provisioned_product['CreatedTime']
        return provisioned_product

    LOGGER.info(f"Did not find {search_pp_name}. Searching for any In-Progress Control Tower Deployments")


def build_service_catalog_parameters(parameters: dict) -> list:
    """Updates the format of the parameters to allow Service Catalog to consume them

    Args:
        parameters (dict): List of parameters in the format of
            {"key1":"value1", "key2":"value2"}

    Returns:
        list: Parameters in the format of {"Key":"string", "Value":"string"}
    """
    new_parameters = []
    for key, value in parameters.items():
        y = {'Key': key, 'Value': value}
        new_parameters.append(y)
    return new_parameters


def get_provisioning_artifact_id(product_name: str, client: boto3.client) -> str:
    """Retrieve the Default Service Catalog Provisioning Artifact ID from the Service Catalog Product specified in
    the definition call.

    Args:
        product_name (str): Service Catalog Product Name
        client (boto3.client): Boto3 Client for Service Catalog

    Returns:
        str: Service Catalog Provisioning Artifact ID
    """
    product_info = client.describe_product(
        Name=product_name
    )
    LOGGER.info(product_info)

    for _product_info in product_info['ProvisioningArtifacts']:
        if _product_info['Guidance'] == 'DEFAULT':
            LOGGER.info(f"Found ProvisioningArtifactId:{_product_info['Id']}")
            return _product_info['Id']


def create_update_provision_product(product_name: str, pp_name: str, pa_id: str, client: boto3.client, params: list,
                                    tags=None, update=False) -> dict:
    """Creates a Service Catalog Provisioned Product

    Args:
        product_name (str): Service Catalog Product Name
        pp_name (str): Service Catalog Provisioned Product Name
        pa_id (str): Service Catalog Provisioned Artifact ID
        client (boto3.client): Boto3 Client for Service Catalog
        params (list): List of Service Catalog Provisioned Product Parameters
        tags (list): List of tags to add to the Service Catalog Provisioned Product
        update (bool) = Does the product need to be updated?

    Returns:
        Return: boto3.client response for service catalog provision product
    """
    param_tags = copy.deepcopy(params)

    # Since there can't be any () within a tag, so we remove them and add a : between the OU name and OU id
    for d in param_tags:
        d.update((k, v.replace(' ', ':').replace('(', '').replace(')', '')) for k, v in d.items() if ("(" and ")") in v)
        d.update((k, f"SCParameter:{v}") for k, v in d.items() if k == "Key")

    if tags:
        for x in param_tags:
            tags.append(x)
    else:
        tags = param_tags

    if update:
        LOGGER.info(f"Updating pp_id:{pp_name} with ProvisionArtifactId:{pa_id} in ProductName:{product_name}")
        sc_response = client.update_provisioned_product(
            ProductName=product_name,
            ProvisionedProductName=pp_name,
            ProvisioningArtifactId=pa_id,
            ProvisioningParameters=params,
            Tags=tags
        )
    else:
        LOGGER.info(f"Creating pp_id:{pp_name} with ProvisionArtifactId:{pa_id} in ProductName:{product_name}")
        sc_response = client.provision_product(
            ProductName=product_name,
            ProvisionedProductName=pp_name,
            ProvisioningArtifactId=pa_id,
            ProvisioningParameters=params,
            Tags=tags
        )

    LOGGER.debug(sc_response)
    return sc_response


def list_children_ous(parent_id: str):
    ou_info = {}
    org = boto3.client('organizations')
    LOGGER.info(f"Getting Children Ous for Id:{parent_id}")
    list_child_paginator = org.get_paginator('list_organizational_units_for_parent')
    for _org_info in list_child_paginator.paginate(ParentId=parent_id):
        for __org_info in _org_info['OrganizationalUnits']:
            ou_info.update({__org_info['Name']: __org_info['Id']})

    LOGGER.info(f"Found OU ID:{ou_info}")
    return ou_info


def get_ou_id(ou_path: str):
    """Gets OU IDs for a particular Organizational Unit

    Args:
        ou_path (str): The Organizational Unit path to get OU ID

    Returns:
        str: AWS Organizations ID
    """
    LOGGER.info("Scanning AWS Organizations for OU Ids")
    org = boto3.client('organizations')
    root_id = org.list_roots()['Roots'][0]['Id']
    if ou_path == 'root':
        LOGGER.debug(f'root_id:{root_id}')
        return root_id

    ou_path_split = ou_path.split(':')
    LOGGER.debug(f'ou_path_split:{ou_path_split}')
    ou_path_len = len(ou_path_split)-1
    LOGGER.debug(f'ou_path_len:{ou_path_len}')

    count = 0
    ou_info = list_children_ous(parent_id=root_id)
    while count < ou_path_len:
        ou_info = list_children_ous(parent_id=ou_info[ou_path_split[count]])
        count = (count + 1)

    return ou_info[ou_path_split[count]]


def tags_to_dict(tags):
    """ Helper for converting the tag structure Boto3 returns into a python dict

    Args:
        tags (list of dict): Tag structure returned from an AWS call

    Returns:
        dict: of tags
    """
    output = {}
    if tags:
        LOGGER.debug(f"Found tags: {tags}")
        for tag in tags:
            output[tag['Key']] = tag['Value']

    return output


def get_service_catalog_tags(prov_product_info: dict):
    all_sc_pp_tags = tags_to_dict(tags=prov_product_info.get('Tags'))

    req_sc_pp_tags = {}
    for k, v in all_sc_pp_tags.items():
        if ("SCParameter:" in k) and (":ou-" in v):
            val = v.split(':')
            req_sc_pp_tags.update({k.replace('SCParameter:', ''): f"{val[0]} ({val[1]})"})

        elif "SCParameter:" in k:
            req_sc_pp_tags.update({k.replace('SCParameter:', ''): v})

    return req_sc_pp_tags