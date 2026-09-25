{{/*
Copyright Broadcom, Inc. All Rights Reserved.
SPDX-License-Identifier: APACHE-2.0
*/}}

{{/* vim: set filetype=mustache: */}}

{{/*
Generate backend entry that is compatible with all Kubernetes API versions.

Usage:
{{ include "common.ingress.backend" (dict "serviceName" "backendName" "servicePort" "backendPort" "context" $) }}

Params:
  - serviceName - String. Name of an existing service backend
  - servicePort - String/Int. Port name (or number) of the service. It will be translated to different yaml depending if it is a string or an integer.
  - context - Dict - Required. The context for the template evaluation.
*/}}
{{- define "common.ingress.backend" -}}
service:
  name: {{ .serviceName }}
  port:
    {{- if typeIs "string" .servicePort }}
    name: {{ .servicePort }}
    {{- else if or (typeIs "int" .servicePort) (typeIs "float64" .servicePort) }}
    number: {{ .servicePort | int }}
    {{- end }}
{{- end -}}

{{/*
Build the ingress annotation that references the middlewares defined in ingress.middlewares.

Returns a dict with a single key (ingress.middlewareAnnotationKey) whose value is the
comma-separated list of <namespace>-<middleware name>@kubernetescrd references in list
order, or an empty dict when no middlewares are defined.

Usage:
{{ include "moodle.ingress.middlewareAnnotations" . }}
*/}}
{{- define "moodle.ingress.middlewareAnnotations" -}}
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
