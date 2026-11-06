#!/bin/bash
set -e

function clean_up() {
    exit_code=$?
    if [ $exit_code -eq 0 ]; then
        echo "=== Finished restore process ==="
        exit $exit_code
    else
        echo "=== An error occurred. Deleting health file: ${health_file} ==="
        rm -f "${health_file}"
        exit $exit_code
    fi
}

trap "clean_up" EXIT

health_file="/tmp/healthy"
RESTORE_DATE="{{ .Values.dbpMoodle.restore.restoreDate }}"

# Create liveness probe file
touch "${health_file}"

{{ if and .Values.dbpMoodle.backup.s3_certificate_secret.enabled }}
printf "Appendending custom certificate (%s/%s) to /etc/ssl/certs/ca-certificates.crt\n" "{{ .Values.dbpMoodle.backup.s3_certificate_secret.mountpath }}" "{{ .Values.dbpMoodle.backup.s3_certificate_secret.key }}"
cat "{{ .Values.dbpMoodle.backup.s3_certificate_secret.mountpath }}/{{ .Values.dbpMoodle.backup.s3_certificate_secret.key }}" >> /etc/ssl/certs/ca-certificates.crt
{{ end }}

# Deployment has "-moodle" appended if the Release.Name does not contain "moodle" 
deployment_name="{{ .Release.Name }}"
if [[ "$deployment_name" != "moodle" && "$deployment_name" != *"moodle"* ]]; then
    deployment_name="${deployment_name}-moodle"
fi

# Get current replicas and scale down deployment
replicas=$(kubectl get "deployment/${deployment_name}" -n {{ .Release.Namespace }} -o=jsonpath='{.status.replicas}')
echo "=== Current replicas detected: $replicas ==="
if [ -z "$replicas" ] || [ "$replicas" -eq 0 ]; then 
    replicas=1
fi
echo "=== Scale moodle deployment to 0 replicas for restore operation ==="
kubectl patch "deployment/${deployment_name}" -n "{{ .Release.Namespace }}" -p '{"spec":{"replicas": 0}}'
echo "=== After restore operation is completed will scale back to: $replicas replicas ==="

# Restore
echo "=== Start duply process ==="
cd /etc/duply/default
for cert in *.asc; do
    echo "=== Import key $cert ==="
    gpg --import --batch $cert
done
for fpr in $(gpg --batch --no-tty --command-fd 0 --list-keys --with-colons  | awk -F: '/fpr:/ {print $10}' | sort -u); do
    echo "=== Trusts key $fpr ==="
    echo -e "5\ny\n" |  gpg --batch --no-tty --command-fd 0 --expert --edit-key $fpr trust;
done

cd /tmp/
echo "=== Download backup ==="
ln -s /etc/duply /home/nonrootuser/.duply
export DUPLY_HOME="/etc/duply"

# Duply restore logic
/usr/bin/duply default restore Full "$RESTORE_DATE"

echo "=== Extract backup files ==="
tar -xzf /tmp/Full/tmp/backup/moodle.tar.gz -C /tmp/ --no-same-owner
tar -xzf /tmp/Full/tmp/backup/moodledata.tar.gz -C /tmp/ --no-same-owner

# Validate the extracted installation before deleting existing files.
if [[ ! -f /tmp/mountData/moodle/config.php ]] ||
    [[ ! -f /tmp/mountData/moodle/public/index.php &&
       ! -f /tmp/mountData/moodle/index.php ]]; then
    echo "=== Backup does not contain a recognizable Moodle installation ===" >&2
    exit 1
fi

if [[ ! -d /tmp/mountData/moodledata ]]; then
    echo "=== Backup does not contain Moodle data ===" >&2
    exit 1
fi

echo "=== Clear PVC ==="
rm -rf /dbp-moodle/moodle/*
rm -rf /dbp-moodle/moodle/.[!.]*
rm -rf /dbp-moodle/moodledata/*
rm -rf /dbp-moodle/moodle/.[!.]*

echo "=== Move backup files ==="
mv /tmp/mountData/moodle/* /dbp-moodle/moodle/
mv /tmp/mountData/moodle/.[!.]* /dbp-moodle/moodle/
mv /tmp/mountData/moodledata/* /dbp-moodle/moodledata/
mv /tmp/mountData/moodledata/.[!.]* /dbp-moodle/moodledata/

cd /dbp-moodle/
echo "=== Clear DB (moodle) ==="
# This command helps with - ERROR: database "moodle" is being accessed by other users
PGPASSWORD="$DATABASE_PASSWORD" psql -h "$DATABASE_HOST" -p "$DATABASE_PORT" -U "$DATABASE_USER" -c "REVOKE CONNECT ON DATABASE ${DATABASE_NAME} FROM public;SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pid <> pg_backend_pid() AND pg_stat_activity.datname = '${DATABASE_NAME}';"
PGPASSWORD="$DATABASE_PASSWORD" psql -h "$DATABASE_HOST" -p "$DATABASE_PORT" -U "$DATABASE_USER" -d postgres -c "DROP DATABASE ${DATABASE_NAME}"
PGPASSWORD="$DATABASE_PASSWORD" psql -h "$DATABASE_HOST" -p "$DATABASE_PORT" -U "$DATABASE_USER" -d postgres -c "CREATE DATABASE ${DATABASE_NAME}"

{{ if eq (default "full" .Values.dbpMoodle.restore.dump_kind) "full" }}
echo "=== Copy dump to DB (moodle) ==="
gunzip /tmp/Full/tmp/backup/moodle_postgresqldb_dump_*
mv /tmp/Full/tmp/backup/moodle_postgresqldb_dump_* /tmp/moodledb_dump.sql

{{ if .Values.dbpMoodle.restore.replace_db_user_during_restore }}
# Only necessary during migration process from local postgres to managed postgres.
# Prior to managed PG database name and user name were 'moodle', post migration they are 'moodle_<instance-name>' so we need to adjust this in the sql commands.
sed -i -e "s/OWNER TO moodle;/OWNER TO {{ .Values.moodle.externalDatabase.user }};/g" /tmp/moodledb_dump.sql
{{ end }}

PGPASSWORD="$DATABASE_PASSWORD" psql -h "$DATABASE_HOST" -p "$DATABASE_PORT" -U "$DATABASE_USER" "$DATABASE_NAME"  < /tmp/moodledb_dump.sql
{{ end }}
{{ if eq .Values.dbpMoodle.restore.dump_kind "custom" }}
echo "=== Copy dump to DB (moodle) ==="
gunzip /tmp/Full/tmp/backup/moodle_postgresqldb_dump_*
mv /tmp/Full/tmp/backup/moodle_postgresqldb_dump_* /tmp/moodledb.dump

PGPASSWORD="$DATABASE_PASSWORD" pg_restore -h "$DATABASE_HOST" -p "$DATABASE_PORT" -U "$DATABASE_USER" -d "$DATABASE_NAME"  --no-owner --no-privileges --disable-triggers /tmp/moodledb.dump
{{ end }}
echo "=== Finished DB restore (moodle) ==="

{{ if .Values.etherpadlite.enabled }}
echo "=== Clear DB (etherpad) ==="
# This command helps with - ERROR: database "moodle" is being accessed by other users
PGPASSWORD="$DATABASE_PASSWORD_ETHERPAD" psql -h "$DATABASE_HOST_ETHERPAD" -p "$DATABASE_PORT_ETHERPAD" -U "$DATABASE_USER_ETHERPAD" -c "REVOKE CONNECT ON DATABASE ${DATABASE_NAME_ETHERPAD} FROM public;SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pid <> pg_backend_pid() AND pg_stat_activity.datname = '${DATABASE_NAME_ETHERPAD}';"
PGPASSWORD="$DATABASE_PASSWORD_ETHERPAD" psql -h "$DATABASE_HOST_ETHERPAD" -p "$DATABASE_PORT_ETHERPAD" -U "$DATABASE_USER_ETHERPAD" -d postgres -c "DROP DATABASE ${DATABASE_NAME_ETHERPAD}"
PGPASSWORD="$DATABASE_PASSWORD_ETHERPAD" psql -h "$DATABASE_HOST_ETHERPAD" -p "$DATABASE_PORT_ETHERPAD" -U "$DATABASE_USER_ETHERPAD" -d postgres -c "CREATE DATABASE ${DATABASE_NAME_ETHERPAD}"
{{ if eq (default "full" .Values.dbpMoodle.restore.dump_kind) "full" }}
echo "=== Copy dump to DB (etherpad) ==="
gunzip /tmp/Full/tmp/backup/etherpad_postgresqldb_dump_*
mv /tmp/Full/tmp/backup/etherpad_postgresqldb_dump_* /tmp/etherpaddb_dump.sql

{{ if .Values.dbpMoodle.restore.replace_db_user_during_restore }}
# Only necessary during migration process from local postgres to managed postgres.
# Prior to managed PG database name and user name were 'etherpad', post migration they are 'etherpad_<instance-name>' so we need to adjust this in the sql commands.
sed -i -e "s/OWNER TO etherpad;/OWNER TO {{ .Values.etherpadlite.externalDatabase.user }};/g" /tmp/etherpaddb_dump.sql
{{ end }}

PGPASSWORD="$DATABASE_PASSWORD_ETHERPAD" psql -h "$DATABASE_HOST_ETHERPAD" -p "$DATABASE_PORT_ETHERPAD" -U "$DATABASE_USER_ETHERPAD" "$DATABASE_NAME_ETHERPAD"  < /tmp/etherpaddb_dump.sql
echo "=== Finished DB restore (etherpad) ==="
{{ end }}
{{ if eq .Values.dbpMoodle.restore.dump_kind "custom" }}
echo "=== Copy dump to DB (etherpad) ==="
gunzip /tmp/Full/tmp/backup/etherpad_postgresqldb_dump_*
mv /tmp/Full/tmp/backup/etherpad_postgresqldb_dump_* /tmp/etherpaddb.dump

PGPASSWORD="$DATABASE_PASSWORD_ETHERPAD" pg_restore -h "$DATABASE_HOST_ETHERPAD" -p "$DATABASE_PORT_ETHERPAD" -U "$DATABASE_USER_ETHERPAD" -d "$DATABASE_NAME_ETHERPAD"  --no-owner --no-privileges --disable-triggers /tmp/etherpaddb.dump
{{ end }}
{{ end }}

echo "=== Scaling deployment replicas to $replicas ==="
kubectl patch "deployment/${deployment_name}" -n "{{ .Release.Namespace }}" --type=merge -p "$(echo "{\"spec\":{\"replicas\":$replicas}}")"

sleep 2
scaledTo=$(kubectl get "deployment/${deployment_name}" -n {{ .Release.Namespace }} -o=jsonpath='{.status.replicas}')
echo "=== Deployment scaled to: $scaledTo ==="