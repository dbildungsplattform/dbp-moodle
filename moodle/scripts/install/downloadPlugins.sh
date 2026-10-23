#!/bin/bash
set -eo pipefail

major_minor="${MOODLE_VERSION%.*}"
plugin_index=0

# The plugin list is shipped in the repo as scripts/install/plugins.json, generated from
# https://download.moodle.org/api/1.3/pluglist.php. That endpoint answers PHP's stream client
# (used by "moosh plugin-list") with 403 from CI runners and also truncates the response every
# few requests, so the list is never fetched at build time. "moosh plugin-download" only ever
# reads the local file, so shipping it is enough.
#
# To pick up new plugin versions, run scripts/install/updatePluginList.sh and commit the result.

# shellcheck source=./pluginList.sh
source "$(dirname "$0")/pluginList.sh"

cd /plugins || exit 1

# Returns non-zero instead of exiting, so download_marketplace_plugin can retry a bad download.
validate_plugin_zip() {
    plugin_name=$1
    plugin_zip="/plugins/${plugin_name}.zip"

    if [ ! -s "$plugin_zip" ]; then
        echo "ERROR: Moodle plugin '$plugin_name' was not downloaded or is empty. Possible download error." >&2
        return 1
    fi

    # A ZIP that cannot be listed (e.g. an HTML error page saved as .zip) must not
    # end up in the image either.
    if ! unzip -tq "$plugin_zip" > /dev/null; then
        echo "ERROR: Moodle plugin '$plugin_name' is not a valid ZIP archive." >&2
        return 1
    fi

    # The root directory inside the ZIP is intentionally NOT checked here - it is not
    # guaranteed to match the plugin directory name. pluginCheck.sh resolves it via version.php.
    # No "grep -q" here: with pipefail enabled, grep -q exiting on the first match
    # kills unzip with SIGPIPE (exit 141) on large archives and fails the check.
    if ! unzip -Z1 "$plugin_zip" | grep -E '(^|/)version\.php$' > /dev/null; then
        echo "ERROR: Moodle plugin '$plugin_name' contains no version.php." >&2
        return 1
    fi
}

check_plugin_zip() {
    validate_plugin_zip "$1" || exit 1
}

# The marketplace intermittently answers with 5xx (e.g. 502 Bad Gateway). "moosh plugin-download"
# still exits 0 and leaves an empty zip behind in that case, so success is judged by the zip itself.
# Retries back off exponentially: 30s, 60s, 120s, ... between attempts.
download_marketplace_plugin() {
    plugin_name=$1
    moodle_version=$2
    max_attempts=5
    retry_delay=30

    for (( attempt = 1; attempt <= max_attempts; attempt++ )); do
        if php -d memory_limit=256M /usr/local/bin/moosh plugin-download -v "$moodle_version" "$plugin_name" \
            && validate_plugin_zip "$plugin_name"; then
            return 0
        fi

        rm -f "/plugins/${plugin_name}.zip"
        if (( attempt < max_attempts )); then
            echo "Download of '$plugin_name' failed (attempt ${attempt}/${max_attempts}). Retrying in ${retry_delay}s..." >&2
            sleep "$retry_delay"
            retry_delay=$((retry_delay * 2))
        fi
    done

    echo "ERROR: Giving up on Moodle plugin '$plugin_name' after ${max_attempts} attempts." >&2
    exit 1
}

# "moosh plugin-download" hardcodes home_dir() . '/.moosh/plugins.json' (there is no -p option)
# and refuses to run when that file is missing, empty, or older than 24h by mtime. Plain cp stamps
# the copy with the current time, so it is fresh enough by construction.
# "$HOME" here resolves exactly like PHP's home_dir() (getenv('HOME')), which reads the same
# variable from the same environment - /root during the image build. The directory has to be
# created: the Dockerfile's "mkdir /.moosh" is a different path, and it used to be "moosh
# plugin-list" that created $HOME/.moosh as a side effect.
install_plugin_list() {
    plugin_list_file="$HOME/.moosh/plugins.json"

    mkdir -p "$HOME/.moosh"
    cp /scripts/install/plugins.json "$plugin_list_file"

    if ! jq -e '.plugins | length > 0' "$plugin_list_file" > /dev/null; then
        echo "ERROR: bundled plugin list scripts/install/plugins.json is not valid JSON or is empty." >&2
        exit 1
    fi

    # plugins.json only holds the components listed in pluginList.sh, so a plugin added there
    # without regenerating it would otherwise fail deep in the loop with moosh's terse
    # "Couldn't find <plugin>". Fail up front with something actionable instead.
    wanted=$(printf '%s\n' "${plugin_list_components[@]}" | jq -R . | jq -sc .)
    missing=$(jq -r --argjson wanted "$wanted" '$wanted - [.plugins[].component] | .[]' \
        "$plugin_list_file")
    if [ -n "$missing" ]; then
        echo "ERROR: plugins.json has no entry for:" >&2
        echo "$missing" >&2
        echo "Run scripts/install/updatePluginList.sh and commit the result." >&2
        exit 1
    fi
}

download_oidc() {
    target_branch="v_45" # eLeDia currently doesn't use any tags, we always use the latest version on branch v_45

    git clone https://github.com/dBildungsplattform/dbp-moodle-plugin-oidc.git
    cd dbp-moodle-plugin-oidc/ || exit 1
    git checkout ${target_branch}
    cat auth/oidc/version.php
    # create the zip archive in the initial directory, s.t. it can be treated equally to the other plugins
    (cd auth && zip -rq ../../eledia_auth_oidc.zip oidc)
    cd ..
    rm -rf dbp-moodle-plugin-oidc/
}

download_boost_magnific() {
    # The marketplace metadata of this plugin has been unreliable (9.6.2 was published as
    # "Moodle 1.9" only, so "moosh plugin-download -v 4.5" refused it). Download a known-good
    # version (9.7.2, supports Moodle 4.4-5.3) directly instead.
    curl -sSfL --retry 5 --retry-delay 10 "https://marketplace.moodle.com/api/plugins/theme_boost_magnific/versions/2026100500/download" \
        -o theme_boost_magnific.zip
}

download_booking() {
    target_tag="v.10.0.5" # sic: this release is tagged with a "v." prefix

    git clone https://github.com/Wunderbyte-GmbH/moodle-mod_booking.git booking
    cd booking/ || exit 1
    git checkout ${target_tag}
    cat version.php
    # create the zip archive in the initial directory, s.t. it can be treated equally to the other plugins
    (cd .. && zip -rq mod_booking.zip booking)
    cd ..
    rm -rf booking/
}

download_course_reminder(){
    target_tag="v1.6.0"
    download_url="https://github.com/krishnaGuptaGit/moodle-local_course_reminder/archive/refs/tags/${target_tag}.zip"

    curl -sSfL "${download_url}" -o local_course_reminder.zip
    echo "Downloaded course_reminder ${target_tag}"
}

# Download a tagged release archive from GitHub as <plugin_name>.zip.
download_github_release() {
    plugin_name=$1
    repo=$2
    tag=$3

    curl -sSfL --retry 5 --retry-delay 10 \
        "https://github.com/${repo}/archive/refs/tags/${tag}.zip" -o "${plugin_name}.zip"
    echo "Downloaded ${plugin_name} ${tag} from github.com/${repo}"
    check_plugin_zip "$plugin_name"
}

# The maintainer withdrew both plugins from the Moodle plugins directory, so they are no longer
# in the plugin list. Latest releases of the MOODLE_405 branches (Moodle 4.5 only).
download_topcoll() {
    download_github_release format_topcoll gjbarnard/moodle-format_topcoll V405.1.5
}

download_adaptable() {
    download_github_release theme_adaptable gjbarnard/moodle-theme_adaptable V405.2.9
}

download_dynamicformat() {
    download_github_release customfield_dynamicformat Wunderbyte-GmbH/moodle-customfield_dynamicformat ines/v1.0.0
}

download_oidc
download_boost_magnific
check_plugin_zip "theme_boost_magnific"
download_booking
download_course_reminder
download_topcoll
download_adaptable
download_dynamicformat
install_plugin_list

for plugin in "${moodle_plugin_list[@]}"; do
    if (( plugin_index > 0 && plugin_index % 1 == 0 )); then
        echo "Reached batch of 1 plugins. Sleeping for 60 seconds..."
        sleep 60
    fi
    download_marketplace_plugin "$plugin" "$major_minor"
    plugin_index=$((plugin_index + 1))
done

# deprecated in release 1.9.1, remove with release >= 1.10
download_marketplace_plugin customfield_dynamic 3.7
