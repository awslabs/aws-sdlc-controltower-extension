#!/usr/bin/env bash

# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

bash scan.sh
bash lint.sh
bash test.sh
bash sam.sh
