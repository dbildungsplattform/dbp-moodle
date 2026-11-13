#!/bin/bash

set -e
image_version="$MOODLE_VERSION"
archive="/tmp/moodle-${image_version}.tgz"

# This trap ensures that the temporary archive is removed on script exit
trap 'rm -f "$archive"' EXIT

# Download Moodle tarball
echo "Downloading Moodle version ${image_version}..."
wget "https://github.com/moodle/moodle/archive/refs/tags/v${image_version}.tar.gz" -O "$archive"

# Extract to target path
echo "Extracting Moodle to ${MOODLE_PATH}..."
mkdir -p "$MOODLE_PATH"
tar -xzf "$archive" --strip-components=1 -C "$MOODLE_PATH" --no-same-owner

# The only new moodle version available is the one we just downloaded
# And is at the MOODLE_PATH (/opt/dbp-moodle/moodle)
echo "Moodle ${image_version} downloaded and extracted successfully."