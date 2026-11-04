{{/*
Copyright Broadcom, Inc. All Rights Reserved.
SPDX-License-Identifier: APACHE-2.0
*/}}

{{/*
Return the proper Moodle&trade; image name
*/}}
{{- define "moodle.image" -}}
{{- include "common.images.image" (dict "imageRoot" .Values.image "global" .Values.global) -}}
{{- end -}}

{{/*
Return the proper Docker Image Registry Secret Names
*/}}
{{- define "moodle.imagePullSecrets" -}}
{{- include "common.images.renderPullSecrets" ( dict "images" (list .Values.image) "context" $ ) -}}
{{- end -}}

{{/*
Return  the proper Storage Class
*/}}
{{- define "moodle.storageClass" -}}
{{- $storageClass := .Values.global.storageClass | default .Values.persistence.storageClass | default .Values.global.defaultStorageClass | default "" -}}
{{- if $storageClass -}}
  {{- if eq $storageClass "-" -}}
    {{- printf "storageClassName: \"\"" -}}
  {{- else -}}
    {{- printf "storageClassName: %s" $storageClass -}}
  {{- end -}}
{{- end -}}
{{- end -}}


{{/*
 Create the name of the service account to use
 */}}
{{- define "moodle.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
    {{ default (include "common.names.fullname" .) .Values.serviceAccount.name }}
{{- else -}}
    {{ default "default" .Values.serviceAccount.name }}
{{- end -}}
{{- end -}}

{{/*
Moodle&trade; credential secret name
*/}}
{{- define "moodle.secretName" -}}
{{- coalesce .Values.existingSecret (include "common.names.fullname" .) -}}
{{- end -}}

{{/*
Return the Database type
*/}}
{{- define "moodle.databaseType" -}}
    {{- printf "%s" .Values.externalDatabase.type -}}
{{- end -}}

{{/*
Return the DB Hostname
*/}}
{{- define "moodle.databaseHost" -}}
    {{- printf "%s" .Values.externalDatabase.host -}}
{{- end -}}

{{/*
Return the DB Port
*/}}
{{- define "moodle.databasePort" -}}
    {{- printf "%d" (.Values.externalDatabase.port | int ) -}}
{{- end -}}

{{/*
Return the Database Name
*/}}
{{- define "moodle.databaseName" -}}
    {{- printf "%s" .Values.externalDatabase.database -}}
{{- end -}}

{{/*
Return the DB User
*/}}
{{- define "moodle.databaseUser" -}}
    {{- printf "%s" .Values.externalDatabase.user -}}
{{- end -}}

{{/*
Return the DB Secret Name
*/}}
{{- define "moodle.databaseSecretName" -}}
    {{- printf "%s" .Values.externalDatabase.existingSecret -}}
{{- end -}}
