#!/bin/bash
set -eo pipefail

major_minor="${MOODLE_VERSION%.*}"
plugin_index=0

# download.moodle.org answers PHP's stream client (used by "moosh plugin-list") with 403 from
# CI runners, while curl is accepted. The plugin list is therefore fetched with curl and the
# version resolution is done with jq instead of moosh.
plugin_list_url="https://download.moodle.org/api/1.3/pluglist.php"
plugin_list_file="/tmp/pluglist.json"
download_user_agent="Mozilla/5.0 (compatible; dbp-moodle-build; +https://github.com/dBildungsplattform/dbp-moodle)"

plugin_dependency_list=(
    local_wunderbyte_table # Dependency of mod_booking
    tool_certificate # Dependency of mod_coursecertificate
    qbehaviour_adaptivemultipart # Dependency of qtype_stack
    qbehaviour_dfexplicitvaildate # Dependency of qtype_stack
    qbehaviour_dfcbmexplicitvaildate # Dependency of qtype_stack
    qbank_importasversion # Dependency of qtype_stack
)

plugin_list=(
    # mod_booking   custom download logic from gh until it is available via marketplace/directory
    # theme_boost_magnific   custom download logic below - the marketplace metadata of its only published version is broken
    # local_course_reminder   custom download logic below - the marketplace metadata of its only published version is broken
    # format_topcoll   custom download logic below - the maintainer withdrew the plugin from the Moodle plugins directory (2026-09)
    # theme_adaptable   custom download logic below - the maintainer withdrew the plugin from the Moodle plugins directory (2026-09)
    theme_boost_union
    mod_choicegroup
    mod_coursecertificate
    mod_etherpadlite
    mod_hvp
    mod_pdfannotator
    format_remuiformat
    local_staticpage
    format_tiles
    mod_unilabel
    block_xp
    mod_zoom
    filter_filtercodes
    filter_shortcodes
    tool_heartbeat
    availability_cohort
    mod_board
    mod_checklist
    block_sharing_cart
    qtype_stack
    block_stash
    block_completion_progress
    tool_coursearchiver
    tool_usersuspension
    tool_dynamic_cohorts
    mod_subcourse
    mod_videotime
    tool_mediatime
    auth_oidc
)

moodle_plugin_list=("${plugin_dependency_list[@]}" "${plugin_list[@]}")

cd /plugins || exit 1

check_plugin_zip() {
    plugin_name=$1
    plugin_zip="/plugins/${plugin_name}.zip"

    if [ ! -s "$plugin_zip" ]; then
        echo "ERROR: Moodle plugin '$plugin_name' was not downloaded or is empty. Possible download error." >&2
        exit 1
    fi

    # A ZIP that cannot be listed (e.g. an HTML error page saved as .zip) must not
    # end up in the image either.
    if ! unzip -tq "$plugin_zip" > /dev/null; then
        echo "ERROR: Moodle plugin '$plugin_name' is not a valid ZIP archive." >&2
        exit 1
    fi

    # The root directory inside the ZIP is intentionally NOT checked here - it is not
    # guaranteed to match the plugin directory name. pluginCheck.sh resolves it via version.php.
    # No "grep -q" here: with pipefail enabled, grep -q exiting on the first match
    # kills unzip with SIGPIPE (exit 141) on large archives and fails the check.
    if ! unzip -Z1 "$plugin_zip" | grep -E '(^|/)version\.php$' > /dev/null; then
        echo "ERROR: Moodle plugin '$plugin_name' contains no version.php." >&2
        exit 1
    fi
}

fetch_plugin_list() {
    curl -sSfL --retry 5 --retry-delay 10 --retry-all-errors \
        -A "$download_user_agent" -H 'Accept: application/json' \
        "$plugin_list_url" -o "$plugin_list_file"
    if ! jq -e '.plugins | length > 0' "$plugin_list_file" > /dev/null; then
        echo "ERROR: plugin list from $plugin_list_url is not valid JSON or is empty." >&2
        exit 1
    fi
}

# Same selection as "moosh plugin-download -v <release>": the highest plugin version that
# lists <release> in its supported Moodle versions. Prints the download URL or fails.
resolve_plugin_url() {
    plugin_name=$1
    release=$2

    url=$(jq -r --arg c "$plugin_name" --arg rel "$release" '
        [ .plugins[] | select(.component == $c) | .versions[]
          | select(any(.supportedmoodles[]; .release == $rel)) ]
        | max_by(.version | tonumber) | .downloadurl // empty' "$plugin_list_file")
    if [ -z "$url" ]; then
        echo "ERROR: no version of Moodle plugin '$plugin_name' supports Moodle $release." >&2
        exit 1
    fi
    echo "$url"
}

download_plugin() {
    plugin_name=$1
    release=$2

    url=$(resolve_plugin_url "$plugin_name" "$release")
    curl -sSfL --retry 5 --retry-delay 10 -A "$download_user_agent" \
        "$url" -o "${plugin_name}.zip"
    echo "Downloaded ${plugin_name} for Moodle ${release} from ${url}"
    check_plugin_zip "$plugin_name"
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
    # The maintainer stopped publishing new versions to the Moodle marketplace; the
    # only remaining published version (9.6.2, requires Moodle >= 4.4) has broken
    # supported-versions metadata ("Moodle 1.9"), so the version resolution for Moodle 4.5
    # refuses it. Download that version directly instead. New releases are only
    # distributed via https://eduardokraus.com/marketplace-plugins/plugin/theme_boost_magnific
    curl -sSfL "https://marketplace.moodle.com/api/plugins/theme_boost_magnific/versions/2026062801/download" \
        -o theme_boost_magnific.zip
}

download_booking() {
    target_tag="v9.7.4-stable"

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
    target_tag="v1.5.2"
    download_url="https://github.com/krishnaGuptaGit/moodle-local_course_reminder/archive/refs/tags/${target_tag}.zip"

    curl -sSfL "${download_url}" -o local_course_reminder.zip
    echo "Downloaded course_reminder ${target_tag}"
}

# Download a tagged release archive from GitHub as <plugin_name>.zip.
download_github_release() {
    plugin_name=$1
    repo=$2
    tag=$3

    curl -sSfL --retry 5 --retry-delay 10 -A "$download_user_agent" \
        "https://github.com/${repo}/archive/refs/tags/${tag}.zip" -o "${plugin_name}.zip"
    echo "Downloaded ${plugin_name} ${tag} from github.com/${repo}"
    check_plugin_zip "$plugin_name"
}

# The maintainer withdrew both plugins from the Moodle plugins directory, so they are no longer
# in the plugin list. Latest releases of the MOODLE_405 branches (Moodle 4.5 only).
download_topcoll() {
    download_github_release format_topcoll gjbarnard/moodle-format_topcoll V405.1.4
}

download_adaptable() {
    download_github_release theme_adaptable gjbarnard/moodle-theme_adaptable V405.2.9
}

download_oidc
download_boost_magnific
check_plugin_zip "theme_boost_magnific"
download_booking
download_course_reminder
download_topcoll
download_adaptable
fetch_plugin_list

for plugin in "${moodle_plugin_list[@]}"; do
    if (( plugin_index > 0 && plugin_index % 15 == 0 )); then
        echo "Reached batch of 15 plugins. Sleeping for 60 seconds..."
        sleep 60
    fi
    download_plugin "$plugin" "$major_minor"
    plugin_index=$((plugin_index + 1))
done

download_plugin customfield_dynamic 3.7
