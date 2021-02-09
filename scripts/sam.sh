#!/usr/bin/env bash

set -e

# (c) 2021 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
# This AWS Content is provided subject to the terms of the AWS Customer Agreement
# available at http://aws.amazon.com/agreement or other written agreement between
# Customer and Amazon Web Services, Inc.

echo "#--------------------------------------------------------#"
echo "#          Building SAM Packages for ${BASE}              "
echo "#--------------------------------------------------------#"

region='us-east-1'
BUCKET=$(aws s3 ls |awk '{print $3}' |grep -E "^controltowerextension-sdlc-[0-9]{12}-${region}")

KMS=$(aws s3api get-bucket-encryption \
  --bucket "${BUCKET}" \
  --region "${region}" \
  --query 'ServerSideEncryptionConfiguration.Rules[*].ApplyServerSideEncryptionByDefault.KMSMasterKeyID' \
  --output text
  )

echo "Deploying Control Tower Extensions - Step Functions"

sam build -t ../lambdas/stepfunctions/cfn.yaml --use-container --region "${region}"

sam package \
  --template-file .aws-sam/build/template.yaml \
  --s3-bucket "${BUCKET}" \
  --s3-prefix "SAM" \
  --kms-key-id "${KMS}" \
  --region "${region}" \
  --output-template-file ../lambdas/stepfunctions/generated-sam-template.yaml

sam deploy \
  --stack-name CTE-SDLC-StepFunctions \
  --template-file ../lambdas/stepfunctions/generated-sam-template.yaml \
  --capabilities CAPABILITY_NAMED_IAM

echo "Deploying Control Tower Extensions - Custom Resources"

sam build -t ../lambdas/custom_resources/cfn.yaml --use-container --region "${region}"

sam package \
  --template-file .aws-sam/build/template.yaml \
  --s3-bucket "${BUCKET}" \
  --s3-prefix "SAM" \
  --kms-key-id "${KMS}" \
  --region "${region}" \
  --output-template-file ../lambdas/custom_resources/generated-sam-template.yaml

sam deploy \
  --stack-name CTE-SDLC-CustomResources \
  --template-file ../lambdas/custom_resources/generated-sam-template.yaml \
  --capabilities CAPABILITY_NAMED_IAM
