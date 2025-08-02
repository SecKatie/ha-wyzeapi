#!/bin/bash

# SPDX-FileCopyrightText: 2024 Katie Mulliken <katie@mulliken.net>
#
# SPDX-License-Identifier: Apache-2.0

TARGET_VERSION=$1

if [ -z "$TARGET_VERSION" ]; then
    echo "Usage: $0 <version>"
    exit 1
fi

# Set the next version as undesired
NEXT_VERSION=$(echo $TARGET_VERSION | awk -F. '{print $1"."$2"."$3+1}')

echo "Constraining version to between $TARGET_VERSION and $NEXT_VERSION"

VERSION_IDENTITY="wyzeapy>=${TARGET_VERSION},<${NEXT_VERSION}"

echo "Setting version to $VERSION_IDENTITY"

uv add "$VERSION_IDENTITY"

tmpfile=$(mktemp)
jq "(.requirements[] | select(. | contains(\"wyzeapy\"))) |= \"$VERSION_IDENTITY\"" custom_components/wyzeapi/manifest.json > "$tmpfile" && mv "$tmpfile" custom_components/wyzeapi/manifest.json