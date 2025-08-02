#!/bin/bash

# SPDX-FileCopyrightText: 2024 Katie Mulliken <katie@mulliken.net>
#
# SPDX-License-Identifier: Apache-2.0

TARGET_VERSION=$1

if [ -z "$TARGET_VERSION" ]; then
    echo "Usage: $0 <version>"
    exit 1
fi

uv version $TARGET_VERSION

tmpfile=$(mktemp)
jq "(.version = \"$TARGET_VERSION\")" custom_components/wyzeapi/manifest.json > "$tmpfile" && mv "$tmpfile" custom_components/wyzeapi/manifest.json

git checkout -b release/$TARGET_VERSION

git add .

git commit -m "chore(release): $TARGET_VERSION"

git push origin release/$TARGET_VERSION