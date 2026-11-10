#!/bin/bash
# This script will be called by the entrypoint.sh on docker image startup and acts as a way to keep our plugins up to date.
# If the PluginsFailed and UpdateFailed signal files do not exist, it will move the plugins from the image to the moodle installation.
# This will ensure that always the most up to date plugins from the image will be used.
set -o errexit
set -o errtrace # required, otherwise the ERR trap is not inherited by functions
set -o nounset
set -o pipefail
# set -o xtrace # Uncomment this line for debugging purposes

# Load Moodle environment
. /scripts/liblog.sh

# Support both the Moodle 4.5 layout and the new public-directory layout.
moodle_path="/dbp-moodle/moodle"
if [[ -f "${moodle_path}/public/index.php" ]]; then
    moodle_path="${moodle_path}/public"
fi

plugin_zip_path="/plugins"
plugin_unzip_path="/tmp/plugins/"

# indicator files
update_plugins_path="/dbp-moodle/moodledata/UpdatePlugins"
update_failed_path="/dbp-moodle/moodledata/UpdateFailed"
update_cli_path="/dbp-moodle/moodledata/CliUpdate"
maintenance_html_path="/dbp-moodle/moodledata/climaintenance.html"

eledia_oidc_plugin_active=false
last_installed_plugin=""
cleanup_failed_install() {
    if [[ -n "$last_installed_plugin" ]]; then
        rm -rf "$last_installed_plugin"
    fi
}

cleanup() {
    if [[ -n "$plugin_unzip_path" ]]; then
        rm -rf "$plugin_unzip_path"
    fi
}

# Extracts <plugin_fullname>.zip and echoes the directory that actually holds the
# plugin sources.
#
# The name of the root directory inside a plugin ZIP is NOT part of any contract.
# Plugins released to the Moodle Marketplace may have a different root directory name (e.g. moodle-local_wunderbyte_table-3.2.8-stable instead of wunderbyte_table). 
# Moodle core itself does not rely on that name either - it renames the extracted root directory while
# installing (see \core\update\code_manager::unzip_plugin_file()).
# Therefore we locate the plugin by its version.php / component instead of guessing.
extract_plugin() {
    local plugin_fullname
    local zip_file
    local dest
    local candidate

    plugin_fullname="$1"
    zip_file="${plugin_zip_path}/${plugin_fullname}.zip"
    dest="${plugin_unzip_path}/${plugin_fullname}"

    if [ ! -s "$zip_file" ]; then
        MODULE="dbp-plugins" error "Plugin archive \"${zip_file}\" is missing or empty."
        return 1
    fi

    rm -rf "${dest:?}"
    mkdir -p "$dest"
    unzip -qo "$zip_file" -d "$dest"

    for candidate in "$dest" "$dest"/*; do
        [ -d "$candidate" ] || continue
        [ -f "${candidate}/version.php" ] || continue
        # The component may be quoted with single or double quotes (e.g.
        # theme_boost_magnific uses double quotes).
        if grep -qE "\\\$plugin->component[[:space:]]*=[[:space:]]*['\"]${plugin_fullname}['\"]" "${candidate}/version.php"; then
            printf '%s' "$candidate"
            return 0
        fi
    done

    MODULE="dbp-plugins" error "Could not find component ${plugin_fullname} inside \"${zip_file}\". Content: $(ls -A "$dest" | tr '\n' ' ')"
    return 1
}

install_plugin() {
    local plugin_fullname
    local plugin_path
    local source_dir

    plugin_fullname="$1"
    plugin_path="$2"

    source_dir="$(extract_plugin "$plugin_fullname")"

    mkdir -p "${moodle_path}/$(dirname "$plugin_path")"
    rm -rf "${moodle_path:?}/${plugin_path:?}"
    cp -a "$source_dir" "${moodle_path}/${plugin_path}"
}

uninstall_plugin() {
    local plugin_fullname
    local plugin_path
    plugin_fullname="$1"
    plugin_path="$2"

    php "${moodle_path}/admin/cli/uninstall_plugins.php" --plugins="$plugin_fullname" --run
    rm -rf "${moodle_path:?}/${plugin_path:?}"
}

upgrade_if_pending() {
    set +o errexit
    result=$(php "${moodle_path}/admin/cli/upgrade.php" --is-pending 2>&1)

    EXIT_CODE=$?
    set -o errexit
    # If an upgrade is needed it exits with an error code of 2 so it distinct from other types of errors.
    if [ $EXIT_CODE -eq 0 ]; then
        MODULE="dbp-plugins" info 'No upgrade needed'
    elif [ $EXIT_CODE -eq 1 ]; then
        MODULE="dbp-plugins" error 'Call to upgrade.php failed... Can not continue installation'
        MODULE="dbp-plugins" error "$result"
        return 1
    elif [ $EXIT_CODE -eq 2 ]; then
        MODULE="dbp-plugins" info 'Running Moodle upgrade'
        php "${moodle_path}/admin/cli/upgrade.php" --non-interactive
    fi
}

get_plugin_version() {
    local plugin_path="$1"
    if [ ! -f "$plugin_path/version.php" ]; then
        return
    fi
    grep -Po '\$plugin->version\s*=\s*\K\d+' "${plugin_path}/version.php" | head -n 1

}

main() {
    if [[ ! -f "${moodle_path}/admin/cli/upgrade.php" ]]; then
        MODULE="dbp-plugins" error "Expected Moodle CLI script at ${moodle_path}/admin/cli/upgrade.php"
        return 1
    fi

    rm -f "$update_plugins_path"

    if [ -d "$plugin_unzip_path" ]; then
        rm -rf "$plugin_unzip_path"
    fi
    mkdir "$plugin_unzip_path"

    anychange=false

    # Update or uninstall third party plugins, depending on the current and target state.
    for plugin in $MOODLE_PLUGINS; do
        IFS=':' read -r -a parts <<< "$plugin"
        plugin_name="${parts[0]}"
        plugin_fullname="${parts[1]}"
        plugin_path="${parts[2]}"
        plugin_target_state="${parts[3]}"

        # This is required to avoid conflicts between eledia oidc and oicd including update and uninstall steps
        if [[ "$plugin_name" = "oidc" && "$eledia_oidc_plugin_active" = true ]]; then
            continue
        fi

        # Check to ensure that only eledia oidc or the original oidc plugin will be installed
        if [[ "$plugin_name" = "eledia_oidc" ]]; then
            if [[ "$plugin_target_state" = true ]]; then
                MODULE="dbp-plugins" info "Eledia oidc plugin is activated, starting preparation of the eledia oidc plugin"
                rm -rf /plugins/auth_oidc.zip
                mv /plugins/eledia_auth_oidc.zip /plugins/auth_oidc.zip || exit 1
                plugin_name="oidc"
                plugin_fullname="auth_oidc"
                eledia_oidc_plugin_active=true
            else
                # if eledia_oidc is not active let the default oidc handle it, to not uninstall it when its actually needed for the standard oidc
                continue
            fi
        fi

        # Build-time unsupported plugins may intentionally have no archive.
        # Do not change their existing files or prevent explicit uninstallations.
        if [[ "$plugin_target_state" = true &&
              ! -s "${plugin_zip_path}/${plugin_fullname}.zip" ]]; then
            MODULE="dbp-plugins" warn "Skipping ${plugin_fullname}: archive unavailable. Existing plugin files are unchanged."
            continue
        fi

        full_path="${moodle_path}/${plugin_path}"

        plugin_cur_state=false

        if [ -d "$full_path" ]; then
            plugin_cur_state=true
        fi

        if [ "$plugin_target_state" = "$plugin_cur_state" ]; then
            # Check if plugin update is required due to newer version in new image
            if [ "$plugin_target_state" = true ]; then
                installed_plugin_version="$(get_plugin_version "$full_path")"
                new_plugin_path="$(extract_plugin "$plugin_fullname")"
                new_plugin_version="$(get_plugin_version "$new_plugin_path")"

                if [ -z "$new_plugin_version" ]; then
                    MODULE="dbp-plugins" error "Could not read version of ${plugin_fullname} from its archive. Aborting."
                    exit 1
                fi

                # An unreadable installed version means the directory exists but does not
                # contain a usable plugin (e.g. an empty directory left behind by a
                # previously failed install). Treat it as "needs to be installed".
                if [ -z "$installed_plugin_version" ]; then
                    MODULE="dbp-plugins" info "Plugin ${plugin_name} is present but has no readable version.php. Reinstalling..."
                    installed_plugin_version=0
                fi

                # Plugin version comparison
                if [ "$new_plugin_version" -gt "$installed_plugin_version" ]; then
                    MODULE="dbp-plugins" info "Plugin ${plugin_name} version changed (installed version: ${installed_plugin_version}, new version: ${new_plugin_version}). Updating..."
                    rm -rf "${moodle_path:?}/${plugin_path:?}"
                    cp -a "$new_plugin_path" "${moodle_path}/${plugin_path}"
                    new_installed_plugin_version="$(get_plugin_version "$full_path")"
                    MODULE="dbp-plugins" info "New installed plugin ${plugin_name} version: ${new_installed_plugin_version}"
                    anychange=true
                else
                    MODULE="dbp-plugins" info "No version change of plugin ${plugin_name} detected or required."
                fi
            fi
            continue
        fi

        if [ "$plugin_target_state" = true ]; then
            last_installed_plugin="$full_path"
            MODULE="dbp-plugins" info "Installing plugin ${plugin_name} (${plugin_fullname}) to path \"${plugin_path}\""
            install_plugin "$plugin_fullname" "$plugin_path"
            last_installed_plugin=""
            anychange=true

        elif [ "$plugin_target_state" = false ]; then
            MODULE="dbp-plugins" info "Uninstalling plugin ${plugin_name} (${plugin_fullname}) from path \"${plugin_path}\""
            uninstall_plugin "$plugin_fullname" "$plugin_path"
            anychange=true
        else
            MODULE="dbp-plugins" error "Unexpected value for plugin_target_state: \"$plugin_target_state\". Expecting \"true/false\". Exiting..."
            exit 1
        fi
    done

    # Uninstall certain standard plugins which are not in use. Whether any plugins are uninstall depends on the content of moodle-plugins config map.
    # Currently not in use but can just be commented in when required.
    # for plugin in $MOODLE_PLUGINS_SYS_UNINSTALL; do
    #     IFS=':' read -r -a parts <<< "$plugin"
    #     plugin_name="${parts[0]}"
    #     plugin_fullname="${parts[1]}"
    #     plugin_path="${parts[2]}"
    #     plugin_uninstall="${parts[3]}"

    #     if [ "$plugin_uninstall" = true ]; then
    #         uninstall_plugin "$plugin_fullname" "$plugin_path"
    #         MODULE="dbp-plugins" info "Uninstalling plugin ${plugin_name} (${plugin_fullname}) from path \"${plugin_path}\""
    #         anychange=true
    #     fi
    # done
    
    
    if [ "$anychange" = true ]; then
        upgrade_if_pending
        php "${moodle_path}/admin/cli/purge_caches.php"
    else
        MODULE="dbp-plugins" info 'No plugin state change detected.'
    fi

    rm -f "$maintenance_html_path" # TODO move this to entrypoint probably
}

trap cleanup_failed_install ERR
trap cleanup EXIT
main