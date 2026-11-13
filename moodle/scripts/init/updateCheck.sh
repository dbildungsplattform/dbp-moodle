#!/bin/bash

set -o errexit
set -o errtrace
set -o nounset
set -o pipefail

. /scripts/liblog.sh

moodle_path="/dbp-moodle/moodle"
current_image_moodle_path="/opt/dbp-moodle/moodle"

# data folders
moodle_backup_path="/dbp-moodle/moodledata/moodle-backup"

# Handles errors during the update process by restoring the backup.
# Is triggered by the ERR trap.
# This creates the directory /dbp-moodle/moodle-failed to store the
# state of the moodle at time of error for debugging purposes.
onErrorRestoreBackup() {
    mv "${moodle_path}" "${moodle_path}-failed"
    cp -rp "${moodle_backup_path}" "${moodle_path}"
}

# return 0 if equal, -1 if $1 > $2 and 1 if $1 < $2
# Required to compare semantic version numbers correctly
compare_semver() {
    local v1="$1"
    local v2="$2"

    v1=$(printf '%03d%03d%03d' ${1//./ })
    v2=$(printf '%03d%03d%03d' ${2//./ })

    if [[ "$v1" == "$v2" ]]; then
        echo "0"
    elif [[ "$v1" > "$v2" ]]; then
        echo "-1"
    elif [[ "$v1" < "$v2" ]]; then
        echo "1"
    fi
}

# Reads the moodle version from the given path out of the version.php file
# $1 - path to the Moodle directory
# Returns the version string in the format X.Y.Z    
get_moodle_version_by_path() {
    local version_file="$1/public/version.php"
    local version

    # Fall back to the layout used by the existing Moodle 4.5 installation.
    if [[ ! -f "$version_file" ]]; then
        version_file="$1/version.php"
    fi

    [[ -f "$version_file" ]] || return 0
    
    version="$(
        grep -P '^\s*\$release\s*=' "$version_file" |
            grep -oP '\d+\.\d+(?:\.\d+)?' |
            head -n 1
    )"

    # Normalize releases without a patch number for compare_semver.
    if [[ "$version" =~ ^[0-9]+\.[0-9]+$ ]]; then
        version="${version}.0"
    fi
    printf '%s\n' "$version"
}

# This does create a local backup of the current Moodle installation before updating.
# The backup is stored in /dbp-moodle/moodledata/moodle-backup
# It does not create a backup of the database, only the Moodle files.
create_backup() {
    if [ -d "$moodle_backup_path" ]; then
        rm -rf "$moodle_backup_path"
    fi
    mkdir -p "$moodle_backup_path"
    tar -czf "${moodle_backup_path}/moodle-backup.tar.gz" -C "${moodle_path}" .
}

# Install the new Moodle version from the current image path (/opt/dbp-moodle/moodle)
# to the default local Moodle path (/dbp-moodle/moodle)
# We only reach this steap after we ensure that the new Moodle version is available and not a symlink.
install_new_version() {
    local image_version="$1"
    MODULE="dbp-update" info "Installing new Moodle (${image_version})"
    mkdir -p "$moodle_path"
    cp -a "${current_image_moodle_path}/." "${moodle_path}/"
}

main() {
    local installed_version new_image_version comp_result

    if [[ -L "${current_image_moodle_path}" || ! -f "${current_image_moodle_path}/public/index.php" ]]; then
        MODULE="dbp-update" error "New Moodle installation is unavailable or already replaced by a persistence symlink"
        exit 1
    fi

    installed_version="$(get_moodle_version_by_path "${moodle_path}")"
    new_image_version="$(get_moodle_version_by_path "${current_image_moodle_path}")"

    if [[ ! "$new_image_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        MODULE="dbp-update" error "Cannot determine the image Moodle version"
        exit 1
    fi

    if [[ -z "$installed_version" ]]; then
        MODULE="dbp-update" info "No installed Moodle version detected, continuing with fresh Moodle install"
        exit 0
    fi

    comp_result="$(compare_semver "$installed_version" "$new_image_version")"
    
    if [[ "$comp_result" == 0 ]]; then
        MODULE="dbp-update" info "Installed version ${installed_version} is same as image version ${new_image_version}"
        exit 0
    fi
    
    if [[ "$comp_result" == 1 ]]; then
        MODULE="dbp-update" info "Starting update of installed version ${installed_version} to ${new_image_version}"
    else
        MODULE="dbp-update" error "Preventing attempted downgrade of installed version ${installed_version} to ${new_image_version}!"
        MODULE="dbp-update" error "Exiting update..."
        exit 1
    fi

    MODULE="dbp-update" info "Creating local backup"
    create_backup

    MODULE="dbp-update" info "Removing old Moodle (${installed_version})"
    rm -rf "${moodle_path:?}"/*
    install_new_version "$new_image_version"
}

trap onErrorRestoreBackup ERR
main
