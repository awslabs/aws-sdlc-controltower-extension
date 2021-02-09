#!/usr/bin/env bash

# (c) 2021 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
# This AWS Content is provided subject to the terms of the AWS Customer Agreement
# available at http://aws.amazon.com/agreement or other written agreement between
# Customer and Amazon Web Services, Inc.

OUTPUT_FILE="logs/scan-output.txt"
echo -n "" > "${OUTPUT_FILE}"

echo "#-----------------------------------------------#" | tee -a "${OUTPUT_FILE}"
echo "#   Scanning Python code for Vulnerabilities     " | tee -a "${OUTPUT_FILE}"
echo "#-----------------------------------------------#" | tee -a "${OUTPUT_FILE}"
echo "Output File: "${OUTPUT_FILE}""
bandit --recursive ../lambdas | tee -a "${OUTPUT_FILE}"

echo "#-----------------------------------------------#" | tee -a "${OUTPUT_FILE}"
echo "#   Scanning Python depend for Vulnerabilities   " | tee -a "${OUTPUT_FILE}"
echo "#-----------------------------------------------#" | tee -a "${OUTPUT_FILE}"
safety check | tee -a "${OUTPUT_FILE}"
