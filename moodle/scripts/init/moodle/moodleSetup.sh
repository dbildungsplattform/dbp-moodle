#!/bin/bash
# Copyright Broadcom, Inc. All Rights Reserved.
# SPDX-License-Identifier: APACHE-2.0

# shellcheck disable=SC1090,SC1091

set -o errexit
set -o nounset
set -o pipefail
# set -o xtrace # Uncomment this line for debugging purposes

# Load Moodle environment
. /scripts/init/moodle/moodle-env.sh

# Load PostgreSQL Client environment for 'postgresql_remote_execute' (after 'discourse-env.sh' so that MODULE is not set to a wrong value)
if [[ -f /scripts/init/postgres/postgres-client-env.sh ]]; then
    . /scripts/init/postgres/postgres-client-env.sh
fi

# Load PHP environment for cron configuration (after 'moodle-env.sh' so that MODULE is not set to a wrong value)
. /scripts/init/php/php-env.sh

# Load libraries
. /scripts/libmoodle.sh
. /scripts/libwebserver.sh

# Load web server environment and functions (after 'moodle-env.sh' file so MODULE is not set to a wrong value)
. "/scripts/init/apache/apache-env.sh"

# Ensure Moodle environment variables are valid
moodle_validate

# Update web server configuration with runtime environment (needs to happen before the initialization)
web_server_update_app_configuration "moodle"

# Ensure Moodle is initialized
moodle_initialize
