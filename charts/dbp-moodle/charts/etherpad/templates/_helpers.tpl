{{/*
Expand the name of the chart.
*/}}
{{- define "etherpad.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "etherpad.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "etherpad.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "etherpad.labels" -}}
helm.sh/chart: {{ include "etherpad.chart" . }}
{{ include "etherpad.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "etherpad.selectorLabels" -}}
app.kubernetes.io/name: {{ include "etherpad.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "etherpad.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "etherpad.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Build the ingress annotation that references the middlewares defined in ingress.middlewares.

Returns a dict with a single key (ingress.middlewareAnnotationKey) whose value is the
comma-separated list of <namespace>-<middleware name>@kubernetescrd references in list
order, or an empty dict when no middlewares are defined.

Usage:
{{ include "etherpad.ingress.middlewareAnnotations" . }}
*/}}
{{- define "etherpad.ingress.middlewareAnnotations" -}}
{{- $refs := list }}
{{- range $mw := .Values.ingress.middlewares }}
{{- $refs = append $refs (printf "%s-%s@kubernetescrd" $.Release.Namespace $mw.name) }}
{{- end }}
{{- if $refs }}
{{- toYaml (dict $.Values.ingress.middlewareAnnotationKey (join ", " $refs)) }}
{{- else }}
{{- toYaml (dict) }}
{{- end }}
{{- end -}}
