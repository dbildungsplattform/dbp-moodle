#!/bin/bash
# Mirrors the plugin archives listed in plugins.json to GitHub Pages, so downloadPlugins.sh can fall
# back to them when "moosh plugin-download" (i.e. download.moodle.org / marketplace.moodle.com) fails.
#
# For every component in pluginList.sh the version "moosh plugin-download -v <release>" would pick
# (highest version whose supportedmoodles contains <release>) is downloaded from the downloadurl in
# plugins.json, verified (md5 from plugins.json, valid ZIP, contains version.php) and stored as
#
#   plugins/<release>/<component>.zip
#   plugins/<release>/index.json        component, version, release, md5 and origin URL of each archive
#
# Published at https://<owner>.github.io/<repo>/plugins/<release>/<component>.zip
#
# Usage:
#   publishPluginMirror.sh              stage the mirror in ./plugin-mirror (or $OUTPUT_DIR), no git
#   publishPluginMirror.sh --publish    commit it to the gh-pages branch (plugins/ only, everything else
#                                       on the branch is left alone) and push it to origin
#
# Environment:
#   MOODLE_RELEASE         Moodle release moosh is called with (default: major.minor of the Dockerfile's
#                          MOODLE_VERSION)
#   OUTPUT_DIR             staging directory when not publishing (default: ./plugin-mirror)
#   PAGES_BRANCH           branch served by GitHub Pages (default: gh-pages)
#   DOWNLOAD_RETRIES       attempts per archive (default: 3)
#   DOWNLOAD_RETRY_DELAY   base delay in seconds, grows linearly (default: 60)
#   DOWNLOAD_PAUSE         pause between two downloads in seconds (default: 10), the marketplace rate-limits
#
# Run scripts/install/updatePluginList.sh first if plugins.json is outdated. The Pages site must be
# configured to serve the $PAGES_BRANCH branch (repository settings -> Pages).
set -eo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
plugins_json="${script_dir}/plugins.json"
dockerfile="${script_dir}/../../Dockerfile"
repo_root="$(git -C "$script_dir" rev-parse --show-toplevel)"

pages_branch="${PAGES_BRANCH:-gh-pages}"
download_retries="${DOWNLOAD_RETRIES:-3}"
download_retry_delay="${DOWNLOAD_RETRY_DELAY:-60}"
download_pause="${DOWNLOAD_PAUSE:-10}"

# The Moodle release customfield_dynamic is pinned to - keep in sync with downloadPlugins.sh.
legacy_moodle_release="3.7"

publish=false
case "${1:-}" in
    "") ;;
    --publish) publish=true ;;
    *) echo "Usage: $0 [--publish]" >&2; exit 2 ;;
esac

# shellcheck source=./pluginList.sh
source "${script_dir}/pluginList.sh"

if [ -z "${MOODLE_RELEASE:-}" ]; then
    moodle_version=$(sed -n 's/^ARG MOODLE_VERSION=.*:-"\([0-9.]*\)".*/\1/p' "$dockerfile" | head -n 1)
    MOODLE_RELEASE="${moodle_version%.*}"
fi
if [ -z "$MOODLE_RELEASE" ]; then
    echo "ERROR: could not determine the Moodle release, set MOODLE_RELEASE." >&2
    exit 1
fi

work_dir=""
cleanup() {
    if [ -n "$work_dir" ]; then
        git -C "$repo_root" worktree remove --force "$work_dir" > /dev/null 2>&1 || true
        rm -rf "$work_dir"
    fi
}
trap cleanup EXIT

if $publish; then
    work_dir=$(mktemp -d)
    if git -C "$repo_root" ls-remote --exit-code --heads origin "$pages_branch" > /dev/null 2>&1; then
        git -C "$repo_root" fetch -q origin "$pages_branch"
        git -C "$repo_root" worktree add -q -B "$pages_branch" "$work_dir" "origin/$pages_branch"
    else
        echo "Branch '$pages_branch' does not exist on origin yet, creating it."
        git -C "$repo_root" worktree add -q --detach "$work_dir"
        git -C "$work_dir" checkout -q --orphan "$pages_branch"
        git -C "$work_dir" rm -rfq .
    fi
    output_dir="${work_dir}/plugins"
else
    output_dir="${OUTPUT_DIR:-$(pwd)/plugin-mirror}"
fi

# Prints "version<TAB>downloadurl<TAB>downloadmd5<TAB>release" of the version moosh picks for
# <component> on Moodle <release>, nothing if there is none.
select_version() {
    jq -r --arg component "$1" --arg release "$2" '
        .plugins[] | select(.component == $component)
        | [ .versions[] | select(any(.supportedmoodles[]?; .release == $release)) ]
        | max_by(.version | tonumber) // empty
        | [ .version, .downloadurl, (.downloadmd5 // ""), .release ] | @tsv' "$plugins_json"
}

# Same checks as check_plugin_zip in downloadPlugins.sh, plus the md5 from plugins.json.
verify_zip() {
    zip=$1
    md5=$2

    [ -s "$zip" ] || return 1
    if [ -n "$md5" ] && [ "$(md5sum "$zip" | cut -d' ' -f1)" != "$md5" ]; then
        echo "  md5 mismatch" >&2
        return 1
    fi
    unzip -tq "$zip" > /dev/null || return 1
    # No "grep -q": with pipefail it would kill unzip with SIGPIPE on large archives.
    unzip -Z1 "$zip" | grep -E '(^|/)version\.php$' > /dev/null || { echo "  no version.php" >&2; return 1; }
}

download_zip() {
    url=$1
    zip=$2
    md5=$3
    attempt=1

    until rm -f "$zip" && curl -sSfL "$url" -o "$zip" && verify_zip "$zip" "$md5"; do
        rm -f "$zip"
        if (( attempt >= download_retries )); then
            return 1
        fi
        wait_seconds=$(( download_retry_delay * attempt ))
        echo "  attempt $attempt/$download_retries failed, retrying in ${wait_seconds}s..." >&2
        sleep "$wait_seconds"
        attempt=$((attempt + 1))
    done
}

# mirror_release <release> <component>...
mirror_release() {
    release=$1
    shift
    release_dir="${output_dir}/${release}"
    index_file=$(mktemp)
    mkdir -p "$release_dir"
    downloaded=false

    for component in "$@"; do
        if ! selected=$(select_version "$component" "$release") || [ -z "$selected" ]; then
            echo "ERROR: plugins.json has no version of '$component' for Moodle $release." >&2
            echo "Run scripts/install/updatePluginList.sh." >&2
            exit 1
        fi
        IFS=$'\t' read -r version url md5 plugin_release <<< "$selected"
        zip="${release_dir}/${component}.zip"

        # Reuse an archive of an earlier run (the gh-pages checkout) if it is still the right one.
        if [ -n "$md5" ] && [ -f "$zip" ] && verify_zip "$zip" "$md5" 2> /dev/null; then
            echo "$component $version: up to date"
        else
            $downloaded && sleep "$download_pause"
            echo "$component $version: downloading $url"
            if ! download_zip "$url" "$zip" "$md5"; then
                echo "ERROR: could not download a valid archive of '$component' from $url." >&2
                exit 1
            fi
            downloaded=true
        fi

        jq -n --arg component "$component" --arg version "$version" --arg release "$plugin_release" \
            --arg md5 "$(md5sum "$zip" | cut -d' ' -f1)" --arg origin "$url" \
            '{component: $component, version: $version, release: $release, md5: $md5, origin: $origin}' \
            >> "$index_file"
    done

    # Archives of components that left the plugin list must not stay online.
    for zip in "$release_dir"/*.zip; do
        [ -e "$zip" ] || continue
        case " $* " in
            *" $(basename "$zip" .zip) "*) ;;
            *) echo "Removing stale $(basename "$zip")"; rm -f "$zip" ;;
        esac
    done

    jq -s 'sort_by(.component)' "$index_file" > "${release_dir}/index.json"
    rm -f "$index_file"
}

mirror_release "$MOODLE_RELEASE" "${moodle_plugin_list[@]}"
mirror_release "$legacy_moodle_release" "${legacy_plugin_list[@]}"

if ! $publish; then
    echo "Staged the plugin mirror in ${output_dir}."
    exit 0
fi

# Without .nojekyll GitHub Pages runs the branch through Jekyll, which is pointless for ZIPs.
touch "${work_dir}/.nojekyll"
git -C "$work_dir" add -A .
if git -C "$work_dir" diff --cached --quiet; then
    echo "Nothing changed, $pages_branch is already up to date."
    exit 0
fi
git -C "$work_dir" commit -q -m "Update plugin mirror (Moodle ${MOODLE_RELEASE})"
git -C "$work_dir" push origin "$pages_branch"
echo "Published to branch ${pages_branch}."
