# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import sys
import mock
import pytest

client_session_helper = mock.Mock()
helper = mock.Mock()

sys.modules["client_session_helper"] = client_session_helper
sys.modules["helper"] = helper


@pytest.fixture()
def upper_creds():
    credentials = {
        "AccessKeyId": 'TEST_UPPER_KEY_ID',
        "SecretAccessKey": 'TEST_UPPER_SECRET',
        "SessionToken": 'TEST_UPPER_SESSION'
    }
    return credentials


@pytest.fixture()
def lower_creds():
    credentials = {
        "accessKeyId": 'TEST_LOWER_KEY_ID',
        "secretAccessKey": 'TEST_LOWER_SECRET',
        "sessionToken": 'TEST_LOWER_SESSION'
    }
    return credentials
