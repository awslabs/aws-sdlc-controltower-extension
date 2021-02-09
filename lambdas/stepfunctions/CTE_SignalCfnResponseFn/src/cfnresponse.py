# (c) 2021 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
# This AWS Content is provided subject to the terms of the AWS Customer Agreement
# available at http://aws.amazon.com/agreement or other written agreement between
# Customer and Amazon Web Services, Inc.

import json
import requests

SUCCESS = "SUCCESS"
FAILED = "FAILED"


def send(event, context, responseStatus, responseData, physicalResourceId=None):
    responseUrl = event['ResponseURL']
    print(responseUrl)
    responseBody = {}
    responseBody['Status'] = responseStatus
    errors = [v for k, v in responseData.items() if 'ERROR' in k]

    if errors:
        # this will only allows 925 characters
        responseBody['Reason'] = f'[CloudWatch Log Stream: {context.log_stream_name}] {errors}'
    else:
        responseBody['Reason'] = 'See the details in CloudWatch Log Stream: ' + context.log_stream_name

    responseBody['PhysicalResourceId'] = physicalResourceId or context.log_stream_name
    responseBody['StackId'] = event['StackId']
    responseBody['RequestId'] = event['RequestId']
    responseBody['LogicalResourceId'] = event['LogicalResourceId']
    responseBody['Data'] = responseData

    json_responseBody = json.dumps(responseBody)

    print("Response body:\n" + json_responseBody)

    headers = {
        'content-type': '',
        'content-length': str(len(json_responseBody))
    }

    try:
        response = requests.put(
            url=responseUrl,
            data=json_responseBody,
            headers=headers
        )
        print("Status code: " + response.reason)

    except Exception as e:
        print("send(..) failed executing requests.put(..): " + str(e))
