from custom_resources.CTE_CrossAccountCloudFormation.src import client_session_helper
import pytest
from moto import mock_sts


@pytest.fixture()
def get_session(upper_creds):
    session = client_session_helper.boto3_session(credentials=upper_creds, region='us-east-1')
    return session


def test_boto3_session_credentials_accesskeyid(upper_creds, mocker, monkeypatch):
    boto3_mock = mocker.Mock()
    monkeypatch.setattr(client_session_helper, "boto3", boto3_mock)
    client_session_helper.boto3_session(
        credentials=upper_creds,
        region='us-east-1'
    )
    boto3_mock.Session.assert_called_once_with(
        aws_access_key_id='TEST_UPPER_KEY_ID',
        aws_secret_access_key='TEST_UPPER_SECRET',
        aws_session_token='TEST_UPPER_SESSION',
        region_name='us-east-1'
    )


def test_boto3_session_credentials_accesskeyid(lower_creds, mocker, monkeypatch):
    boto3_mock = mocker.Mock()
    monkeypatch.setattr(client_session_helper, "boto3", boto3_mock)
    client_session_helper.boto3_session(
        credentials=lower_creds,
        region='us-east-1'
    )
    boto3_mock.Session.assert_called_once_with(
        aws_access_key_id='TEST_LOWER_KEY_ID',
        aws_secret_access_key='TEST_LOWER_SECRET',
        aws_session_token='TEST_LOWER_SESSION',
        region_name='us-east-1'
    )


@mock_sts
def test_boto3_session_credentials_accesskeyid(mocker, monkeypatch):
    boto3_mock = mocker.Mock()
    monkeypatch.setattr(client_session_helper, "boto3", boto3_mock)
    client_session_helper.boto3_session(
        profile='mock-profile',
        region='us-east-1'
    )
    boto3_mock.Session.assert_called_once_with(
        profile_name='mock-profile',
        region_name='us-east-1'
    )


def test_boto3_client_profile(mocker, monkeypatch):
    boto3_session_mock = mocker.Mock()
    session_mock = mocker.Mock()
    boto3_session_mock.return_value = session_mock
    monkeypatch.setattr(client_session_helper, "boto3_session", boto3_session_mock)
    client_session_helper.boto3_client(
        service='ec2',
        profile='mock_test',
        region='us-east-1'
    )
    boto3_session_mock.assert_called_once_with('mock_test')
    session_mock.client.assert_called_once_with(
        region_name='us-east-1',
        service_name='ec2'
    )


def test_boto3_client_assumed_credentials_accesskeyid(upper_creds, mocker, monkeypatch):
    boto3_session_mock = mocker.Mock()
    session_mock = mocker.Mock()
    boto3_session_mock.return_value = session_mock
    monkeypatch.setattr(client_session_helper, "boto3_session", boto3_session_mock)
    client_session_helper.boto3_client(
        service='s3',
        assumed_credentials=upper_creds,
        region='us-east-1'
    )
    boto3_session_mock.assert_called_once_with(None)
    session_mock.client.assert_called_once_with(
        aws_access_key_id='TEST_UPPER_KEY_ID',
        aws_secret_access_key='TEST_UPPER_SECRET',
        aws_session_token='TEST_UPPER_SESSION',
        region_name='us-east-1',
        service_name='s3'
    )


def test_boto3_client_assumed_credentials_accesskeyid(lower_creds, mocker, monkeypatch):
    boto3_session_mock = mocker.Mock()
    session_mock = mocker.Mock()
    boto3_session_mock.return_value = session_mock
    monkeypatch.setattr(client_session_helper, "boto3_session", boto3_session_mock)
    client_session_helper.boto3_client(
        service='iam',
        assumed_credentials=lower_creds,
        region='us-east-1'
    )
    boto3_session_mock.assert_called_once_with(None)
    session_mock.client.assert_called_once_with(
        aws_access_key_id='TEST_LOWER_KEY_ID',
        aws_secret_access_key='TEST_LOWER_SECRET',
        aws_session_token='TEST_LOWER_SESSION',
        region_name='us-east-1',
        service_name='iam'
    )


def test_boto3_client_session(get_session, mocker, monkeypatch):
    boto3_session_mock = mocker.Mock()
    session_mock = mocker.Mock()
    get_session.return_value = session_mock
    monkeypatch.setattr(client_session_helper, "boto3_session", boto3_session_mock)
    client_session_helper.boto3_client(
        service='ec2',
        session=session_mock,
        region='us-east-1'
    )
    boto3_session_mock.assert_not_called()
    session_mock.client.assert_called_once_with(
        region_name='us-east-1',
        service_name='ec2'
    )


def test_boto3_client_no_service(mocker, monkeypatch):
    with pytest.raises(BaseException) as client_error:
        client_session_helper.boto3_client()
    assert "boto3_client() missing 1 required positional argument: 'service'" in str(client_error.value)
