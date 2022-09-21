#!/usr/bin/env bash

# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

if [ -d .aws-sam ]; then
  echo "[INFO] Removing .aws-sam directory"
  rm -rf .aws-sam
fi

echo "#------------------------------------------------------------------------------------#"
echo "#   Building / Deploying SAM Packages for  Control Tower Extension - Create Account   "
echo "#------------------------------------------------------------------------------------#"

region='us-east-1'
BUCKET=$(aws s3 ls |awk '{print $3}' |grep -E "^controltowerextension-sdlc-[0-9]{12}-${region}")

# If S3 Bucket was not found, echo aws command to run to create it
if [ -z "${BUCKET}" ]; then
  echo "[ERROR] No \"controltowerextension-sdlc\" S3 Bucket found, please run the following command to provision the required Bucket. Then re-run scripts/sam.sh script."
  export LOCAL_ROLE_ARN=$(aws sts get-caller-identity --query 'Arn' --output text | sed -e 's/assumed-//g' | sed -e 's/\/botocore-session-[0-9]*//g')
  echo "aws cloudformation deploy --stack-name SDLC-ControlTowerExtension-Bootstrap --template-file cloudformation/sam-bootstrap.yaml --parameter-overrides pRoleArn=${LOCAL_ROLE_ARN} --capabilities CAPABILITY_NAMED_IAM"
  exit 1
fi

# Get KMS Key from S3 Bucket
echo "[INFO] Getting Encryption Key for S3 Bucket"
KMS=$(aws s3api get-bucket-encryption \
  --bucket "${BUCKET}" \
  --region "${region}" \
  --query 'ServerSideEncryptionConfiguration.Rules[*].ApplyServerSideEncryptionByDefault.KMSMasterKeyID' \
  --output text
  )

# Get Portfolio Id for Account Factory in Service Catalog
PORTFOLIO_ID=$(aws servicecatalog list-portfolios \
    --query 'PortfolioDetails[?starts_with(DisplayName, `AWS Control Tower Account Factory Portfolio`)].Id' \
    --output text)

# Stopping script if there's a failure
set -e

echo "[INFO] Using Bucket:${BUCKET} KMS:${KMS} for SAM Deployment"

echo "[INFO] Building Infrastructure Serverless Application Function (lambdas/stepfunctions/serverless.yaml)"
sam build -t lambdas/stepfunctions/serverless.yaml --use-container --region "${region}"

echo "[INFO] Deploying Infrastructure Serverless Application Function (lambdas/stepfunctions/serverless.yaml)"
sam deploy \
  --config-file lambdas/stepfunctions/serverless.toml \
  --s3-bucket "${BUCKET}" \
  --kms-key-id "${KMS}" \
  --parameter-overrides "pControlTowerPortfolioId=${PORTFOLIO_ID}" \
  --no-fail-on-empty-changeset

echo "[INFO] Building Infrastructure Serverless Application Function (lambdas/custom_resources/serverless.yaml)"
sam build -t lambdas/custom_resources/serverless.yaml --use-container --region "${region}"

echo "[INFO] Deploying Infrastructure Serverless Application Function (lambdas/custom_resources/serverless.yaml)"
sam deploy \
  --config-file lambdas/custom_resources/serverless.toml \
  --s3-bucket "${BUCKET}" \
  --kms-key-id "${KMS}" \
  --no-fail-on-empty-changeset

# Updating Service Catalog Portfolio Associated Principal
#echo "[INFO] Getting Local Role Arn"
#LOCAL_ROLE_ARN=$(aws sts get-caller-identity --query 'Arn' --output text | sed -e 's/assumed-//g' | sed -e 's/\/botocore-session-[0-9]*//g')
#echo "[INFO] Adding local used to "
#aws servicecatalog associate-principal-with-portfolio \
#  --portfolio-id "${PORTFOLIO_ID}" \
#  --principal-arn "${LOCAL_ROLE_ARN}" \
#  --principal-type IAM