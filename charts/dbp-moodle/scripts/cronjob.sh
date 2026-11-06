#!/bin/bash
set -e

health_file="/tmp/healthy"

# Create liveness probe file
touch "${health_file}"

function clean_up() {
    exit_code=$?
    if [ $exit_code -eq 0 ]; then
        echo "Command 'php ./dbp-moodle/moodle/admin/cli/cron.php' has been run on pod [${moodle_pod}]!"
    else
        echo "An error occurred. Deleting health file: ${health_file}"
        rm -f "${health_file}"
    fi
    exit $exit_code
}

trap "clean_up" EXIT

moodle_pod=$(kubectl -n {{ .Release.Namespace }} get pods -l app.kubernetes.io/name=moodle -o jsonpath='{.items[0].metadata.name}')

echo "Waiting for pod [${moodle_pod}] to be ready..."
kubectl -n "{{ .Release.Namespace }}" wait --for=condition=Ready pod/"${moodle_pod}" --timeout={{ .Values.dbpMoodle.moodlecronjob.wait_timeout }}
echo "Executing cron command in pod: ${moodle_pod}"
kubectl exec -n "{{ .Release.Namespace }}" "${moodle_pod}" -- sh -ec '
    moodle_path="/dbp-moodle/moodle"
    if [ -f "${moodle_path}/public/index.php" ]; then
        moodle_path="${moodle_path}/public"
    fi

    cron_script="${moodle_path}/admin/cli/cron.php"
    if [ ! -f "$cron_script" ]; then
        echo "Moodle cron script not found: ${cron_script}" >&2
        exit 1
    fi

    exec php "$cron_script"
'
