#!/bin/bash
# Regenerates scripts/install/plugins.json, the plugin list "moosh plugin-download" reads at image
# build time. Run this to pick up new plugin versions, or after adding a plugin to pluginList.sh,
# and commit the result.
#
# The upstream response is ~14 MB covering ~2900 plugins; it is reduced to the components in
# pluginList.sh and pretty-printed, which keeps the committed file small enough that a refresh
# costs the repository almost nothing and shows up as a readable diff.
set -eo pipefail

api_url="https://download.moodle.org/api/1.3/pluglist.php"
script_dir="$(cd "$(dirname "$0")" && pwd)"
target="${script_dir}/plugins.json"

# shellcheck source=./pluginList.sh
source "${script_dir}/pluginList.sh"

tmp_file=$(mktemp)
trap 'rm -f "$tmp_file"' EXIT

# The endpoint truncates the response every few requests and still exits 0, so the download is
# retried until the JSON parses and looks complete rather than trusted on the first try.
for attempt in 1 2 3 4 5; do
    echo "Fetching ${api_url} (attempt ${attempt})..."
    if curl -sSfL --retry 3 --retry-delay 5 "$api_url" -o "$tmp_file" \
        && jq -e '.plugins | length > 2000' "$tmp_file" > /dev/null 2>&1; then
        break
    fi
    echo "  incomplete or unparseable response ($(wc -c < "$tmp_file") bytes), retrying..." >&2
    if [ "$attempt" = 5 ]; then
        echo "ERROR: could not fetch a complete plugin list from ${api_url}." >&2
        exit 1
    fi
    sleep 5
done

wanted=$(printf '%s\n' "${plugin_list_components[@]}" | jq -R . | jq -sc .)

jq -S --argjson wanted "$wanted" '
    { timestamp: .timestamp
    , plugins: [ .plugins[] | select(.component as $c | $wanted | index($c)) ]
    }' "$tmp_file" > "$target"

missing=$(jq -r --argjson wanted "$wanted" '$wanted - [.plugins[].component] | .[]' "$target")
if [ -n "$missing" ]; then
    echo "ERROR: the Moodle plugins directory has no entry for:" >&2
    echo "$missing" >&2
    echo "Either the component name in pluginList.sh is wrong, or the plugin was withdrawn and" >&2
    echo "needs custom download logic in downloadPlugins.sh." >&2
    exit 1
fi

echo "Wrote ${target}: $(jq '.plugins | length' "$target") plugins, $(wc -c < "$target") bytes."
