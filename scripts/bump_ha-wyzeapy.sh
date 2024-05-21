#!/bin/bash

TARGET_VERSION=$1

if [ -z "$TARGET_VERSION" ]; then
    echo "Usage: $0 <version>"
    exit 1
fi

poetry version $TARGET_VERSION

tmpfile=$(mktemp)
jq "(.version = \"$TARGET_VERSION\")" custom_components/wyzeapi/manifest.json > "$tmpfile" && mv "$tmpfile" custom_components/wyzeapi/manifest.json

git checkout -b release/$TARGET_VERSION

git add .

git commit -m "chore(release): $TARGET_VERSION"

git push origin release/$TARGET_VERSION