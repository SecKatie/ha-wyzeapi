#!/bin/bash

# SPDX-FileCopyrightText: 2021 Joshua Mulliken <joshua@mulliken.net>
#
# SPDX-License-Identifier: Apache-2.0

mkdir -p .test
git clone git@github.com:home-assistant/core.git .test/core
mkdir -p .test/core/config/custom_components
cp -R custom_components/wyzeapi .test/core/config/custom_components/wyzeapi
cd .test/core
script/setup