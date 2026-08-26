{{- define "dbpMoodle.moodlePvc.name" -}}
{{- if .Values.dbpMoodle.external_pvc.enabled }}
{{- .Values.dbpMoodle.external_pvc.name -}}
{{- else if .Values.moodle.persistence.enabled }}
{{- .Release.Name }}-moodle
{{- else }}
{{- printf "Warning: Neither external_pvc nor moodle.persistence is enabled, using default value 'moodle-moodle' which will probably fail." }}
"moodle-moodle"
{{- end -}}
{{- end -}}

{{- define "dbpMoodle.hpa.deployment_name_ref" -}}
{{- default "moodle" .Values.dbpMoodle.hpa.deployment_name_ref }}
{{- end -}}

{{- define "moodlecronjob.job_name" -}}
{{- with (index .Values.moodlecronjob.jobs 0) -}}
{{- .name -}}
{{- end -}}
{{- end -}}

{{- define "backup-cronjob.job_name" -}}
{{- $releasename := .Release.Name -}} 
{{- with (index .Values "backup-cronjob" "jobs") -}}
{{- printf "%s-backup-cronjob-%s" $releasename (index . 0).name -}}
{{- end -}}
{{- end -}}

{{- define "dbpMoodle.secrets.moodle_password" -}}
{{- default (randAlphaNum 16) .Values.dbpMoodle.secrets.moodle_password }}
{{- end -}}

{{- define "dbpMoodle.secrets.moodle_user" -}}
{{- default "moodle" .Values.dbpMoodle.secrets.moodle_user }}
{{- end -}}

{{- define "dbpMoodle.secrets.database_password" -}}
    {{- default (randAlphaNum 16) .Values.dbpMoodle.secrets.database_password }}
{{- end -}}

{{- define "dbpMoodle.secrets.database_user" -}}
{{- default "moodle" .Values.dbpMoodle.secrets.database_user }}
{{- end -}}

{{- define "dbpMoodle.secrets.database_name" -}}
{{- default "moodle" .Values.dbpMoodle.secrets.database_name }}
{{- end -}}

{{- define "dbpMoodle.secrets.database_admin_password" -}}
{{- default (randAlphaNum 32) .Values.dbpMoodle.secrets.database_root_password }}
{{- end -}}

{{- define "dbpMoodle.secrets.redis_password" -}}
{{- default (randAlphaNum 16) .Values.dbpMoodle.secrets.redis_password }}
{{- end -}}

{{- define "dbpMoodle.secrets.etherpad_postgresql_password" -}}
{{- default (randAlphaNum 16) .Values.dbpMoodle.secrets.etherpad_postgresql_password }}
{{- end -}}

{{- define "dbpMoodle.secrets.etherpad_api_key" -}}
{{- default (randAlphaNum 16) .Values.dbpMoodle.secrets.etherpad_api_key }}
{{- end -}}

{{- define "dbpMoodle.backup.retention_time" -}}
{{- default "6M" .Values.dbpMoodle.backup.retention_time }}
{{- end -}}

{{- define "dbpMoodle.backup.max_full_backup_age" -}}
{{- default "1W" .Values.dbpMoodle.backup.max_full_backup_age }}
{{- end -}}

{{- define "dbpMoodle.sessionStore.enabled" -}}
{{- if or .Values.redis.enabled (.Values.valkey).enabled -}}true{{- end -}}
{{- end -}}

{{- define "dbpMoodle.pluginConfigMap.content" -}}
eledia_oidc:eledia_auth_oidc:auth/oidc:                         {{- .Values.global.moodlePlugins.eledia_oidc.enabled }}{{"\n"}}
wunderbyte_table:local_wunderbyte_table:local/wunderbyte_table: {{- .Values.global.moodlePlugins.booking.enabled}}{{"\n"}}
certificate:tool_certificate:admin/tool/certificate:            {{- or .Values.global.moodlePlugins.certificate.enabled .Values.global.moodlePlugins.coursecertificate.enabled }}{{"\n"}}
etherpadlite:mod_etherpadlite:mod/etherpadlite:                 {{- .Values.global.moodlePlugins.etherpadlite.enabled }}{{"\n"}}
hvp:mod_hvp:mod/hvp:                                            {{- .Values.global.moodlePlugins.hvp.enabled }}{{"\n"}}
groupselect:mod_groupselect:mod/groupselect:                    {{- .Values.global.moodlePlugins.groupselect.enabled }}{{"\n"}}
jitsi:mod_jitsi:mod/jitsi:                                      {{- .Values.global.moodlePlugins.jitsi.enabled }}{{"\n"}}
pdfannotator:mod_pdfannotator:mod/pdfannotator:                 {{- .Values.global.moodlePlugins.pdfannotator.enabled }}{{"\n"}}
skype:mod_skype:mod/skype:                                      {{- .Values.global.moodlePlugins.skype.enabled }}{{"\n"}}
zoom:mod_zoom:mod/zoom:                                         {{- .Values.global.moodlePlugins.zoom.enabled }}{{"\n"}}
booking:mod_booking:mod/booking:                                {{- .Values.global.moodlePlugins.booking.enabled }}{{"\n"}}
reengagement:mod_reengagement:mod/reengagement:                 {{- .Values.global.moodlePlugins.reengagement.enabled }}{{"\n"}}
unilabel:mod_unilabel:mod/unilabel:                             {{- .Values.global.moodlePlugins.unilabel.enabled }}{{"\n"}}
geogebra:mod_geogebra:mod/geogebra:                             {{- .Values.global.moodlePlugins.geogebra.enabled }}{{"\n"}}
choicegroup:mod_choicegroup:mod/choicegroup:                    {{- .Values.global.moodlePlugins.choicegroup.enabled }}{{"\n"}}
staticpage:local_staticpage:local/staticpage:                   {{- .Values.global.moodlePlugins.staticpage.enabled }}{{"\n"}}
heartbeat:tool_heartbeat:admin/tool/heartbeat:                  {{- .Values.global.moodlePlugins.heartbeat.enabled }}{{"\n"}}
remuiformat:format_remuiformat:course/format/remuiformat:       {{- .Values.global.moodlePlugins.remuiformat.enabled }}{{"\n"}}
tiles:format_tiles:course/format/tiles:                         {{- .Values.global.moodlePlugins.tiles.enabled }}{{"\n"}}
topcoll:format_topcoll:course/format/topcoll:                   {{- .Values.global.moodlePlugins.topcoll.enabled }}{{"\n"}}
flexsections:format_flexsections:format/flexsections:           {{- .Values.global.moodlePlugins.flexsections.enabled }}{{"\n"}}
multitopic:format_multitopic:format/multitopic:                 {{- .Values.global.moodlePlugins.multitopic.enabled }}{{"\n"}}
oidc:auth_oidc:auth/oidc:                                       {{- .Values.global.moodlePlugins.oidc.enabled }}{{"\n"}}
saml2:auth_saml2:auth/saml2:                                    {{- .Values.global.moodlePlugins.saml2.enabled }}{{"\n"}}
dash:block_dash:blocks/dash:                                    {{- .Values.global.moodlePlugins.dash.enabled }}{{"\n"}}
sharing_cart:block_sharing_cart:blocks/sharing_cart:            {{- .Values.global.moodlePlugins.sharing_cart.enabled }}{{"\n"}}
xp:block_xp:blocks/xp:                                          {{- .Values.global.moodlePlugins.xp.enabled }}{{"\n"}}
coursecertificate:mod_coursecertificate:mod/coursecertificate:  {{- .Values.global.moodlePlugins.coursecertificate.enabled }}{{"\n"}}
adaptable:theme_adaptable:theme/adaptable:                      {{- .Values.global.moodlePlugins.adaptable.enabled }}{{"\n"}}
boost_union:theme_boost_union:theme/boost_union:                {{- .Values.global.moodlePlugins.boost_union.enabled }}{{"\n"}}
boost_magnific:theme_boost_magnific:theme/boost_magnific:       {{- .Values.global.moodlePlugins.boost_magnific.enabled }}{{"\n"}}
snap:theme_snap:theme/snap:                                     {{- .Values.global.moodlePlugins.snap.enabled }}{{"\n"}}
usersuspension:tool_usersuspension:admin/tool/usersuspension:   {{- .Values.global.moodlePlugins.usersuspension.enabled }}{{"\n"}}
dynamic_cohorts:tool_dynamic_cohorts:admin/tool/dynamic_cohorts:{{- .Values.global.moodlePlugins.dynamic_cohorts.enabled }}{{"\n"}}
shortcodes:filter_shortcodes:filter/shortcodes:                 {{- .Values.global.moodlePlugins.shortcodes.enabled }}{{"\n"}}
filtercodes:filter_filtercodes:filter/filtercodes:              {{- .Values.global.moodlePlugins.filtercodes.enabled }}{{"\n"}}
dynamic:customfield_dynamic:customfield/field/dynamic:          {{- .Values.global.moodlePlugins.customfield_dynamic.enabled }}{{"\n"}}
cohort:availability_cohort:availability/condition/cohort:       {{- .Values.global.moodlePlugins.availability_cohort.enabled }}{{"\n"}}
board:mod_board:mod/board:                                      {{- .Values.global.moodlePlugins.board.enabled }}{{"\n"}}
adaptivemultipart:qbehaviour_adaptivemultipart:question/behaviour/adaptivemultipart: {{- .Values.global.moodlePlugins.qtype_stack.enabled }}{{"\n"}}
dfexplicitvaildate:qbehaviour_dfexplicitvaildate:question/behaviour/dfexplicitvaildate: {{- .Values.global.moodlePlugins.qtype_stack.enabled }}{{"\n"}}
dfcbmexplicitvaildate:qbehaviour_dfcbmexplicitvaildate:question/behaviour/dfcbmexplicitvaildate: {{- .Values.global.moodlePlugins.qtype_stack.enabled }}{{"\n"}}
importasversion:qbank_importasversion:/question/bank/importasversion: {{- .Values.global.moodlePlugins.qtype_stack.enabled }}{{"\n"}}
stack:qtype_stack:question/type/stack:                          {{- .Values.global.moodlePlugins.qtype_stack.enabled }}{{"\n"}}
checklist:mod_checklist:mod/checklist:                          {{- .Values.global.moodlePlugins.mod_checklist.enabled }}{{"\n"}}
stash:block_stash:blocks/stash:                                 {{- .Values.global.moodlePlugins.block_stash.enabled }}{{"\n"}}
completion_progress:block_completion_progress:blocks/completion_progress: {{- .Values.global.moodlePlugins.completion_progress.enabled }}{{"\n"}}
coursearchiver:tool_coursearchiver:admin/tool/coursearchiver:   {{- .Values.global.moodlePlugins.coursearchiver.enabled }}{{"\n"}}
subcourse:mod_subcourse:mod/subcourse:                          {{- .Values.global.moodlePlugins.mod_subcourse.enabled }}{{"\n"}}
videotime:mod_videotime:mod/videotime:                          {{- .Values.global.moodlePlugins.mod_videotime.enabled }}{{"\n"}}
mediatime:tool_mediatime:admin/tool/mediatime:                  {{- .Values.global.moodlePlugins.tool_mediatime.enabled }}{{"\n"}}
course_reminder:local_course_reminder:local/course_reminder:    {{- .Values.global.moodlePlugins.local_course_reminder.enabled }}{{"\n"}}
{{- end -}}

{{- define "dbpMoodle.pluginConfigMap.sys.uninstall.content" -}}
{{- if .Values.dbpMoodle.uninstallSystemPlugins }}
dropbox:repository_dropbox:repository/dropbox:                      {{- "true" }}{{"\n"}}
equella:repository_equella:repository/equella:                      {{- "true" }}{{"\n"}}
filesystem:repository_filesystem:repository/filesystem:             {{- "true" }}{{"\n"}}
flickr:repository_flickr:repository/flickr:                         {{- "true" }}{{"\n"}}
flickr_public:repository_flickr_public:repository/flickr_public:    {{- "true" }}{{"\n"}}
googledocs:repository_googledocs:repository/googledocs:             {{- "true" }}{{"\n"}}
merlot:repository_merlot:repository/merlot:                         {{- "true" }}{{"\n"}}
onedrive:repository_onedrive:repository/onedrive:                   {{- "true" }}{{"\n"}}
s3:repository_s3:repository/s3:                                     {{- "true" }}{{"\n"}}
webdav:repository_webdav:repository/webdav:                         {{- "true" }}{{"\n"}}
youtube:repository_youtube:repository/youtube:                      {{- "true" }}{{"\n"}}
flickr:portfolio_flickr:portfolio/flickr:                           {{- "true" }}{{"\n"}}
mahara:portfolio_mahara:portfolio/mahara:                           {{- "true" }}{{"\n"}}
smsgateway_aws:smsgateway_aws:smsgateway/aws:                       {{- "true" }}{{"\n"}}
enrol_paypal:enrol_paypal:enrol/paypal:                             {{- "true" }}{{"\n"}}
unoconv:fileconverter_unoconv:fileconverter/unoconv:                {{- "true" }}{{"\n"}}
{{- end -}}
{{- end -}}

{{- define "dbpMoodle.backup.gpg_key_names.cmd" -}}
{{- $keys := .Values.dbpMoodle.backup.gpg_key_names -}}
{{- range $index, $key := $keys -}}
$(gpg --show-keys --with-colons /etc/duply/default/gpgkey.{{ $key }}.pub.asc | awk -F: '/^pub/ { print $5 }'){{- if lt (add1 $index) (len $keys) -}},{{- end -}}
{{- end -}}
{{- end -}}