#!/bin/bash
# Copyright Broadcom, Inc. All Rights Reserved.
# SPDX-License-Identifier: APACHE-2.0

# shellcheck disable=SC1091

set -o errexit
set -o nounset
set -o pipefail
# set -o xtrace # Uncomment this line for debugging purposes

# Load libraries
. /scripts/libfs.sh
. /scripts/liblog.sh
. /scripts/libapache.sh

# Load Apache environment
. /scripts/init/apache/apache-env.sh

# Ensure Apache environment variables are valid
apache_validate

# Ensure Apache daemon user exists when running as 'root'
am_i_root && ensure_user_exists "$APACHE_DAEMON_USER" --group "$APACHE_DAEMON_GROUP"

# Define custom certs directory
SSL_CERTS_DIR="/opt/dbp-moodle/apache/certs"

# Generate SSL certs (without a passphrase)
mkdir -p "$SSL_CERTS_DIR"
if [[ ! -f "$SSL_CERTS_DIR/tls.crt" || ! -f "$SSL_CERTS_DIR/tls.key" ]]; then
    echo "Generating sample certificates"
    SSL_KEY_FILE="$SSL_CERTS_DIR/tls.key"
    SSL_CERT_FILE="$SSL_CERTS_DIR/tls.crt"
    SSL_CSR_FILE="$SSL_CERTS_DIR/tls.csr"
    SSL_SUBJ="/CN=example.com"
    SSL_EXT="subjectAltName=DNS:example.com,DNS:www.example.com,IP:127.0.0.1"

    rm -f "$SSL_KEY_FILE" "$SSL_CERT_FILE"
    openssl genrsa -out "$SSL_KEY_FILE" 4096

    if [[ "$(openssl version | grep -oE "[0-9]+\.[0-9]+")" == "1.0" ]]; then
        openssl req -new -sha256 -out "$SSL_CSR_FILE" -key "$SSL_KEY_FILE" -nodes -subj "$SSL_SUBJ"
    else
        openssl req -new -sha256 -out "$SSL_CSR_FILE" -key "$SSL_KEY_FILE" -nodes -subj "$SSL_SUBJ" -addext "$SSL_EXT"
    fi

    openssl x509 -req -sha256 -in "$SSL_CSR_FILE" -signkey "$SSL_KEY_FILE" -out "$SSL_CERT_FILE" -days 1825 -extfile <(echo -n "$SSL_EXT")
    rm -f "$SSL_CSR_FILE"
fi

# Update ports in configuration
[[ -n "$APACHE_HTTP_PORT_NUMBER" ]] && info "Configuring the HTTP port" && apache_configure_http_port "$APACHE_HTTP_PORT_NUMBER"
[[ -n "$APACHE_HTTPS_PORT_NUMBER" ]] && info "Configuring the HTTPS port" && apache_configure_https_port "$APACHE_HTTPS_PORT_NUMBER"

# Configure Apache Security settings
[[ -n "$APACHE_SERVER_TOKENS" ]] && info "Configuring Apache ServerTokens directive and ServerSignature" && apache_configure_security_settings "$APACHE_SERVER_TOKENS" "$APACHE_SERVER_SIGNATURE"
#rm -rf "$APACHE_SECURITY_FILE"

# Fix logging issue when running as root
! am_i_root || chmod o+w "$(readlink /dev/stdout)" "$(readlink /dev/stderr)"
