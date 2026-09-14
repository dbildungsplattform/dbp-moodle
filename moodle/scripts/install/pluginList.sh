# Single source of truth for the plugins downloaded from the Moodle plugins directory.
# Sourced by downloadPlugins.sh (at image build time) and by updatePluginList.sh (which uses it
# to decide what to keep when refreshing plugins.json). Plugins with custom download logic are
# deliberately not listed here - see the comments in downloadPlugins.sh.

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

# Plugins pinned to an older Moodle release than the one being built - see downloadPlugins.sh.
legacy_plugin_list=(
    customfield_dynamic
)

moodle_plugin_list=("${plugin_dependency_list[@]}" "${plugin_list[@]}")

# Everything that has to be resolvable from plugins.json.
plugin_list_components=("${moodle_plugin_list[@]}" "${legacy_plugin_list[@]}")
