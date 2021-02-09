#!/usr/bin/env bash

# (c) 2021 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
# This AWS Content is provided subject to the terms of the AWS Customer Agreement
# available at http://aws.amazon.com/agreement or other written agreement between
# Customer and Amazon Web Services, Inc.

set -eo pipefail

echo "#---------------------------------------------------#"
echo "#                  Running Tests                     "
echo "#---------------------------------------------------#"

for test in $(find .. -name tox.ini); do
  #pyenv local 3.6.9 3.7.4 3.8.1  # Can do multiple versions like this but need to make sure they are installed
  tox -c "${test}"
done
