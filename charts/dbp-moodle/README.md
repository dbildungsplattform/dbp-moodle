# dbp-moodle

![Version: 1.6.6](https://img.shields.io/badge/Version-1.6.6-informational?style=flat-square) ![Type: application](https://img.shields.io/badge/Type-application-informational?style=flat-square) ![AppVersion: 4.5.12](https://img.shields.io/badge/AppVersion-4.5.12-informational?style=flat-square)

This is a Helm Chart bundling some of the bitnami resources to deploy Moodle for DBildungsplattform. Extending them with features such as
PostgreSQL support, Horizontal Autoscaling capabilities, Redis Session Store, Etherpad-Lite.
The Chart can be deployed without any modification but it is advised to set own secrets acccording to this readme.

**Homepage:** <https://dbildungsplattform.github.io/dbp-moodle/>

## Requirements

| Repository | Name | Version |
|------------|------|---------|
| file://charts/cronjob | cronjob | 0.1.0 |
| file://charts/cronjob | cronjob | 0.1.0 |
| file://charts/etherpad | etherpad | 0.1.0 |
| file://charts/moodle | moodle | 27.0.5 |
| https://burningalchemist.github.io/sql_exporter/ | sql-exporter | 0.6.1 |
| https://charts.bitnami.com/bitnami | postgresql | 15.5.38 |
| https://charts.bitnami.com/bitnami | postgresql | 15.5.38 |
| https://charts.bitnami.com/bitnami | redis | 19.5.3 |
| https://wiremind.github.io/wiremind-helm-charts | clamav | 3.5.0 |

## Values

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| backup-cronjob.affinity | object | `{}` |  |
| backup-cronjob.clusterRole.create | bool | `false` |  |
| backup-cronjob.env[0].name | string | `"DATABASE_HOST"` |  |
| backup-cronjob.env[0].valueFrom.secretKeyRef.key | string | `"host"` |  |
| backup-cronjob.env[0].valueFrom.secretKeyRef.name | string | `"moodle-database"` |  |
| backup-cronjob.env[10].name | string | `"AWS_ACCESS_KEY_ID"` |  |
| backup-cronjob.env[10].valueFrom.secretKeyRef.key | string | `"s3_access_key"` |  |
| backup-cronjob.env[10].valueFrom.secretKeyRef.name | string | `"moodle-backup-s3"` |  |
| backup-cronjob.env[11].name | string | `"AWS_SECRET_ACCESS_KEY"` |  |
| backup-cronjob.env[11].valueFrom.secretKeyRef.key | string | `"s3_access_secret"` |  |
| backup-cronjob.env[11].valueFrom.secretKeyRef.name | string | `"moodle-backup-s3"` |  |
| backup-cronjob.env[12].name | string | `"S3_BACKUP_REGION_URL"` |  |
| backup-cronjob.env[12].valueFrom.secretKeyRef.key | string | `"s3_endpoint_url"` |  |
| backup-cronjob.env[12].valueFrom.secretKeyRef.name | string | `"moodle-backup-s3"` |  |
| backup-cronjob.env[1].name | string | `"DATABASE_PORT"` |  |
| backup-cronjob.env[1].valueFrom.secretKeyRef.key | string | `"port"` |  |
| backup-cronjob.env[1].valueFrom.secretKeyRef.name | string | `"moodle-database"` |  |
| backup-cronjob.env[2].name | string | `"DATABASE_NAME"` |  |
| backup-cronjob.env[2].valueFrom.secretKeyRef.key | string | `"name"` |  |
| backup-cronjob.env[2].valueFrom.secretKeyRef.name | string | `"moodle-database"` |  |
| backup-cronjob.env[3].name | string | `"DATABASE_USER"` |  |
| backup-cronjob.env[3].valueFrom.secretKeyRef.key | string | `"user"` |  |
| backup-cronjob.env[3].valueFrom.secretKeyRef.name | string | `"moodle-database"` |  |
| backup-cronjob.env[4].name | string | `"DATABASE_PASSWORD"` |  |
| backup-cronjob.env[4].valueFrom.secretKeyRef.key | string | `"mariadb-password"` |  |
| backup-cronjob.env[4].valueFrom.secretKeyRef.name | string | `"moodle"` |  |
| backup-cronjob.env[5].name | string | `"DATABASE_HOST_ETHERPAD"` |  |
| backup-cronjob.env[5].valueFrom.secretKeyRef.key | string | `"host"` |  |
| backup-cronjob.env[5].valueFrom.secretKeyRef.name | string | `"etherpad-database"` |  |
| backup-cronjob.env[6].name | string | `"DATABASE_PORT_ETHERPAD"` |  |
| backup-cronjob.env[6].valueFrom.secretKeyRef.key | string | `"port"` |  |
| backup-cronjob.env[6].valueFrom.secretKeyRef.name | string | `"etherpad-database"` |  |
| backup-cronjob.env[7].name | string | `"DATABASE_NAME_ETHERPAD"` |  |
| backup-cronjob.env[7].valueFrom.secretKeyRef.key | string | `"name"` |  |
| backup-cronjob.env[7].valueFrom.secretKeyRef.name | string | `"etherpad-database"` |  |
| backup-cronjob.env[8].name | string | `"DATABASE_USER_ETHERPAD"` |  |
| backup-cronjob.env[8].valueFrom.secretKeyRef.key | string | `"user"` |  |
| backup-cronjob.env[8].valueFrom.secretKeyRef.name | string | `"etherpad-database"` |  |
| backup-cronjob.env[9].name | string | `"DATABASE_PASSWORD_ETHERPAD"` |  |
| backup-cronjob.env[9].valueFrom.secretKeyRef.key | string | `"etherpad-postgresql-password"` |  |
| backup-cronjob.env[9].valueFrom.secretKeyRef.name | string | `"moodle"` |  |
| backup-cronjob.extraVolumeMounts[0].mountPath | string | `"/scripts/"` |  |
| backup-cronjob.extraVolumeMounts[0].name | string | `"moodle-backup-script"` |  |
| backup-cronjob.extraVolumeMounts[1].mountPath | string | `"/mountData"` |  |
| backup-cronjob.extraVolumeMounts[1].name | string | `"moodle-pvc-data"` |  |
| backup-cronjob.extraVolumeMounts[2].mountPath | string | `"/etc/duply/default/"` |  |
| backup-cronjob.extraVolumeMounts[2].name | string | `"duply"` |  |
| backup-cronjob.extraVolumes[0].name | string | `"moodle-pvc-data"` |  |
| backup-cronjob.extraVolumes[0].persistentVolumeClaim.claimName | string | `"moodle-data"` |  |
| backup-cronjob.extraVolumes[1].configMap.defaultMode | int | `457` |  |
| backup-cronjob.extraVolumes[1].configMap.name | string | `"moodle-backup-script"` |  |
| backup-cronjob.extraVolumes[1].name | string | `"moodle-backup-script"` |  |
| backup-cronjob.extraVolumes[2].name | string | `"duply"` |  |
| backup-cronjob.extraVolumes[2].projected.defaultMode | int | `420` |  |
| backup-cronjob.extraVolumes[2].projected.sources[0].configMap.items[0].key | string | `"conf"` |  |
| backup-cronjob.extraVolumes[2].projected.sources[0].configMap.items[0].path | string | `"conf"` |  |
| backup-cronjob.extraVolumes[2].projected.sources[0].configMap.items[1].key | string | `"exclude"` |  |
| backup-cronjob.extraVolumes[2].projected.sources[0].configMap.items[1].path | string | `"exclude"` |  |
| backup-cronjob.extraVolumes[2].projected.sources[0].configMap.name | string | `"moodle-backup-duply"` |  |
| backup-cronjob.extraVolumes[2].projected.sources[1].secret.name | string | `"moodle-backup-gpg-keys"` |  |
| backup-cronjob.image.repository | string | `"ghcr.io/dbildungsplattform/moodle-tools"` |  |
| backup-cronjob.image.tag | string | `"1.1.15"` |  |
| backup-cronjob.jobs[0].args[0] | string | `"/scripts/backup-script"` |  |
| backup-cronjob.jobs[0].command[0] | string | `"/bin/sh"` |  |
| backup-cronjob.jobs[0].command[1] | string | `"-c"` |  |
| backup-cronjob.jobs[0].failedJobsHistoryLimit | int | `1` |  |
| backup-cronjob.jobs[0].livenessProbe.exec.command[0] | string | `"cat"` |  |
| backup-cronjob.jobs[0].livenessProbe.exec.command[1] | string | `"/tmp/healthy"` |  |
| backup-cronjob.jobs[0].livenessProbe.initialDelaySeconds | int | `5` |  |
| backup-cronjob.jobs[0].livenessProbe.periodSeconds | int | `10` |  |
| backup-cronjob.jobs[0].name | string | `"backup"` |  |
| backup-cronjob.jobs[0].schedule | string | `"0 3 * * *"` |  |
| backup-cronjob.jobs[0].successfulJobsHistoryLimit | int | `1` |  |
| backup-cronjob.podSecurityContext.fsGroup | int | `1001` |  |
| backup-cronjob.resources.limits.cpu | string | `"2000m"` |  |
| backup-cronjob.resources.limits.memory | string | `"4Gi"` |  |
| backup-cronjob.resources.requests.cpu | string | `"500m"` |  |
| backup-cronjob.resources.requests.memory | string | `"1Gi"` |  |
| backup-cronjob.securityContext.allowPrivilegeEscalation | bool | `false` |  |
| backup-cronjob.securityContext.capabilities.drop[0] | string | `"ALL"` |  |
| backup-cronjob.securityContext.privileged | bool | `false` |  |
| backup-cronjob.securityContext.runAsGroup | int | `1001` |  |
| backup-cronjob.serviceAccount.create | bool | `false` |  |
| backup-cronjob.serviceAccount.name | string | `"moodle-backup-job"` |  |
| backup-cronjob.tolerations | list | `[]` |  |
| clamav.affinity | object | `{}` |  |
| clamav.enabled | bool | `true` |  |
| clamav.freshclamConfig | string | `"Bytecode yes\nDatabaseDirectory /data\nDatabaseMirror database.clamav.net\nDatabaseOwner 1001\nLogTime yes\nNotifyClamd /etc/clamav/clamd.conf\nPidFile /tmp/freshclam.pid\nScriptedUpdates yes\n"` |  |
| clamav.hpa.enabled | bool | `false` |  |
| clamav.image.pullPolicy | string | `"IfNotPresent"` |  |
| clamav.image.tag | string | `"1.5.1"` |  |
| clamav.kind | string | `"StatefulSet"` |  |
| clamav.podSecurityContext.fsGroup | int | `1001` |  |
| clamav.podSecurityContext.runAsGroup | int | `1001` |  |
| clamav.podSecurityContext.runAsNonRoot | bool | `true` |  |
| clamav.podSecurityContext.runAsUser | int | `1001` |  |
| clamav.resources.limits.cpu | string | `"1000m"` |  |
| clamav.resources.limits.memory | string | `"4Gi"` |  |
| clamav.resources.requests.cpu | string | `"200m"` |  |
| clamav.resources.requests.memory | string | `"2Gi"` |  |
| clamav.securityContext.allowPrivilegeEscalation | bool | `false` |  |
| clamav.securityContext.capabilities.drop[0] | string | `"ALL"` |  |
| clamav.securityContext.privileged | bool | `false` |  |
| clamav.securityContext.runAsNonRoot | bool | `true` |  |
| clamav.service.port | int | `3310` |  |
| clamav.service.type | string | `"ClusterIP"` |  |
| clamav.tolerations | list | `[]` |  |
| dbpMoodle.allowInternalNetworkingOnly | bool | `false` | disallows all egress from release namespace for the moodle deployment |
| dbpMoodle.backup | object | `{"cluster_name":"","dump_kind":"full","enabled":false,"endpoint":"","gpg_key_names":[],"gpgkeys":{"existingSecret":"","gpgkey.devops.pub.asc":"","gpgkey.devops.sec.asc":""},"max_full_backup_age":"1W","retention_time":"6M","rules":[{"apiGroups":["apps"],"resources":["deployments"],"verbs":["get","patch","list","watch"]},{"apiGroups":["batch"],"resources":["cronjobs","jobs"],"verbs":["get","patch"]}],"run_pre_upgrade":true,"s3_bucket_name":"","s3_certificate_secret":{"enabled":false,"key":"certificate.crt","mountpath":"/certs","name":"s3-certificate"},"secrets":{"existingSecret":"","s3_access_key":"","s3_access_secret":"","s3_endpoint_url":""}}` | Backup configuration. Set enabled=true to enable the backup-cronjob. Also set s3 location credentials |
| dbpMoodle.backup.gpg_key_names | list | `[]` | Provide a List of keys like: gpg_key_names: ["devops", "fallback"] |
| dbpMoodle.backup.gpgkeys | object | `{"existingSecret":"","gpgkey.devops.pub.asc":"","gpgkey.devops.sec.asc":""}` | If the gpgkeys values that are provided (gpgkey.devops.pub.asc) are filled with keys, and no existingSecret is provided -- a secret will be created and the "gpg_key_names" value should be set to "devops" to match the created keys identifier |
| dbpMoodle.backup.gpgkeys.existingSecret | string | `""` | Existing  secret for gpg keys, make sure the keys identifier is set in "gpg_key_names" for the backup to work properly -- Example: gpgkey.devops.pub.asc  -> gpg_key_names: ["devops"] -- If no value is set, a secret will be created with the keys from the values above |
| dbpMoodle.backup.max_full_backup_age | string | `"1W"` | Defines the maximum age of a full backup before a new full backup is created. The backups in between are incremental |
| dbpMoodle.backup.retention_time | string | `"6M"` | Defines the maximum age of a backup before it is deleted |
| dbpMoodle.backup.s3_certificate_secret | object | `{"enabled":false,"key":"certificate.crt","mountpath":"/certs","name":"s3-certificate"}` | Secret key of a certificate for duply to connect to s3 endpoint using SSL, useful to trust self-signed certificates -- certificate has to mounted "manually" under values backup-cronjob |
| dbpMoodle.backup.s3_certificate_secret.key | string | `"certificate.crt"` | Path where the certificate is mounted |
| dbpMoodle.backup.secrets | object | `{"existingSecret":"","s3_access_key":"","s3_access_secret":"","s3_endpoint_url":""}` | Either provide an existing secret, or set each secret value here. If both are set the existingSecret is used |
| dbpMoodle.backup.secrets.existingSecret | string | `""` | Existing secret for s3 endpoint |
| dbpMoodle.external_pvc.accessModes[0] | string | `"ReadWriteMany"` |  |
| dbpMoodle.external_pvc.annotations."helm.sh/resource-policy" | string | `"keep"` |  |
| dbpMoodle.external_pvc.enabled | bool | `true` |  |
| dbpMoodle.external_pvc.name | string | `"moodle-data"` |  |
| dbpMoodle.external_pvc.size | string | `"8Gi"` |  |
| dbpMoodle.external_pvc.storage_class | string | `"nfs-client"` |  |
| dbpMoodle.goemaxima.enabled | bool | `false` |  |
| dbpMoodle.goemaxima.env.MAXIMA_TIMEOUT | string | `"30"` |  |
| dbpMoodle.goemaxima.image.pullPolicy | string | `"IfNotPresent"` |  |
| dbpMoodle.goemaxima.image.repository | string | `"ghcr.io/dbildungsplattform/goemaxima"` |  |
| dbpMoodle.goemaxima.image.tag | string | `"2026080600-master-20260811"` |  |
| dbpMoodle.goemaxima.podSecurityContext | object | `{}` |  |
| dbpMoodle.goemaxima.replicaCount | int | `1` |  |
| dbpMoodle.goemaxima.resources.limits.cpu | string | `"1"` |  |
| dbpMoodle.goemaxima.resources.limits.memory | string | `"512Mi"` |  |
| dbpMoodle.goemaxima.resources.requests.cpu | string | `"200m"` |  |
| dbpMoodle.goemaxima.resources.requests.memory | string | `"256Mi"` |  |
| dbpMoodle.goemaxima.securityContext.allowPrivilegeEscalation | bool | `false` |  |
| dbpMoodle.goemaxima.securityContext.readOnlyRootFilesystem | bool | `true` |  |
| dbpMoodle.goemaxima.securityContext.runAsNonRoot | bool | `true` |  |
| dbpMoodle.goemaxima.securityContext.runAsUser | int | `1000` |  |
| dbpMoodle.goemaxima.securityContext.seccompProfile.type | string | `"RuntimeDefault"` |  |
| dbpMoodle.goemaxima.service.annotations | object | `{}` |  |
| dbpMoodle.goemaxima.service.labels | object | `{}` |  |
| dbpMoodle.goemaxima.service.port | int | `8080` |  |
| dbpMoodle.goemaxima.service.targetPort | int | `8080` |  |
| dbpMoodle.goemaxima.service.type | string | `"ClusterIP"` |  |
| dbpMoodle.hpa | object | `{"average_cpu_utilization":50,"deployment_name_ref":"moodle","enabled":false,"max_replicas":4,"min_replicas":1,"scaledown_cooldown":60,"scaledown_value":25,"scaleup_cooldown":15,"scaleup_value":50}` | Horizontal pod autoscaling values |
| dbpMoodle.hpa.scaledown_cooldown | int | `60` | How many seconds to wait between downscaling adjustments |
| dbpMoodle.hpa.scaledown_value | int | `25` | The max amount in percent to scale down in one step per cooldown period |
| dbpMoodle.hpa.scaleup_cooldown | int | `15` | How many seconds to wait between upscaling adjustments |
| dbpMoodle.hpa.scaleup_value | int | `50` | The max amount in percent to scale up in one step per cooldown period |
| dbpMoodle.moodleUpdatePreparationHook.rules[0].apiGroups[0] | string | `"apps"` |  |
| dbpMoodle.moodleUpdatePreparationHook.rules[0].resources[0] | string | `"deployments"` |  |
| dbpMoodle.moodleUpdatePreparationHook.rules[0].verbs[0] | string | `"get"` |  |
| dbpMoodle.moodleUpdatePreparationHook.rules[0].verbs[1] | string | `"patch"` |  |
| dbpMoodle.moodleUpdatePreparationHook.rules[1].apiGroups[0] | string | `"batch"` |  |
| dbpMoodle.moodleUpdatePreparationHook.rules[1].resources[0] | string | `"cronjobs"` |  |
| dbpMoodle.moodleUpdatePreparationHook.rules[1].resources[1] | string | `"jobs"` |  |
| dbpMoodle.moodleUpdatePreparationHook.rules[1].verbs[0] | string | `"get"` |  |
| dbpMoodle.moodleUpdatePreparationHook.rules[1].verbs[1] | string | `"list"` |  |
| dbpMoodle.moodleUpdatePreparationHook.rules[1].verbs[2] | string | `"create"` |  |
| dbpMoodle.moodleUpdatePreparationHook.rules[1].verbs[3] | string | `"patch"` |  |
| dbpMoodle.moodleUpdatePreparationHook.rules[1].verbs[4] | string | `"watch"` |  |
| dbpMoodle.moodleUpdatePreparationJob | object | `{"affinity":{},"enabled":false,"image":"moodle-tools","repository":"ghcr.io/dbildungsplattform","resources":{},"tag":"1.1.15","tolerations":[]}` | A preperation job which disables the php-cronjob, scales down the deployment and creates a backup if dbpMoodle.backup.enabled=true |
| dbpMoodle.moodleUpdatePreparationJob.repository | string | `"ghcr.io/dbildungsplattform"` | Which kubectl image to use |
| dbpMoodle.moodlecronjob | object | `{"rules":[{"apiGroups":[""],"resources":["pods","pods/exec"],"verbs":["get","list","create","watch"]}],"wait_timeout":"15m"}` | Configuration for the moodle-cronjob which runs moodles cron.php. This is required since moodle does not run as root |
| dbpMoodle.name | string | `"infra"` |  |
| dbpMoodle.phpConfig.additional | string | `""` | Any additional text to be included into the config.php |
| dbpMoodle.phpConfig.additionalPhpIni | string | `"memory_limit = 513M\nupload_max_filesize = 201M\npost_max_size = 150M\n"` | A string filled with additional php.ini configuration that overwrites the default one |
| dbpMoodle.phpConfig.debug | bool | `false` | Moodle debugging is not safe for production |
| dbpMoodle.phpConfig.existingConfig | string | `""` | Provide an existing secret containing the config.php instead of generating it from chart -- Remember to adjust moodle.extraVolumes & moodle.extraVolumeMounts when setting this. -- Secret key is by default expected to be config.php |
| dbpMoodle.phpConfig.extendedLogging | bool | `false` | Extended php logging |
| dbpMoodle.phpConfig.ip.allowed | string | `""` |  |
| dbpMoodle.phpConfig.ip.blocked | string | `""` |  |
| dbpMoodle.phpConfig.pluginUIInstallation | object | `{"enabled":false}` | Prevents the installation of Plugins from the Moodle Web Interface for Admins (Disabled by default) |
| dbpMoodle.redis | object | `{"host":"moodle-redis-master","port":6379}` | Configurations for the optional redis |
| dbpMoodle.restore | object | `{"affinity":{},"dump_kind":"full","enabled":false,"existingSecretDatabaseConfig":"moodle-database","existingSecretDatabasePassword":"moodle","existingSecretGPG":"","existingSecretKeyDatabasePassword":"","existingSecretKeyS3Access":"","existingSecretKeyS3Secret":"","existingSecretS3":"","image":"moodle-tools","podSecurityContext":{"fsGroup":1001},"replace_db_user_during_restore":false,"repository":"ghcr.io/dbildungsplattform","resources":{"limits":{"cpu":"2000m","memory":"4Gi"},"requests":{"cpu":"1000m","memory":"2Gi"}},"restoreDate":"","rules":[{"apiGroups":["apps"],"resources":["deployments/scale","deployments"],"verbs":["get","list","patch"]}],"securityContext":{"allowPrivilegeEscalation":false,"capabilities":{"drop":["ALL"]},"privileged":false,"runAsGroup":1001},"tag":"1.1.15","tolerations":[]}` | This restores moodle to the latest snapshot. Requires an existing s3 backup. ONLY USE FOR ROLLBACK |
| dbpMoodle.secrets | object | `{"database_admin_password":"","database_name":"","database_password":"","database_root_password":"","database_user":"","etherpad_api_key":"","etherpad_postgresql_password":"","moodle_password":"","moodle_user":"","redis_password":"","useChartSecret":true}` | Creates a secret with all relevant credentials for moodle -- Set useChartSecret: false to provide your own secret -- If you create your own secret, also set moodle.existingSecret (and moodle.externalDatabase.existingSecret if you bring your own DB) |
| dbpMoodle.stage | string | `"infra"` |  |
| dbpMoodle.uninstallSystemPlugins | bool | `false` |  |
| etherpad-postgresql.auth.database | string | `"etherpad"` |  |
| etherpad-postgresql.auth.enablePostgresUser | bool | `false` |  |
| etherpad-postgresql.auth.existingSecret | string | `"moodle"` |  |
| etherpad-postgresql.auth.secretKeys.userPasswordKey | string | `"etherpad-postgresql-password"` |  |
| etherpad-postgresql.auth.username | string | `"etherpad"` |  |
| etherpad-postgresql.enabled | bool | `false` |  |
| etherpad-postgresql.image.repository | string | `"bitnamilegacy/postgresql"` |  |
| etherpad-postgresql.image.tag | string | `"14.18.0-debian-12-r0"` |  |
| etherpad-postgresql.metrics.image.repository | string | `"bitnamilegacy/postgres-exporter"` |  |
| etherpad-postgresql.persistence.existingClaim | string | `"moodle-etherpad-postgresql"` |  |
| etherpad-postgresql.primary.affinity | object | `{}` |  |
| etherpad-postgresql.primary.containerSecurityContext.privileged | bool | `false` |  |
| etherpad-postgresql.primary.resources.limits.cpu | string | `"1000m"` |  |
| etherpad-postgresql.primary.resources.limits.memory | string | `"1Gi"` |  |
| etherpad-postgresql.primary.resources.requests.cpu | string | `"50m"` |  |
| etherpad-postgresql.primary.resources.requests.memory | string | `"128Mi"` |  |
| etherpad-postgresql.primary.tolerations | list | `[]` |  |
| etherpad-postgresql.volumePermissions.image.repository | string | `"bitnamilegacy/os-shell"` |  |
| etherpadlite.affinity | object | `{}` |  |
| etherpadlite.enabled | bool | `false` |  |
| etherpadlite.env[0].name | string | `"DB_TYPE"` |  |
| etherpadlite.env[0].value | string | `"postgres"` |  |
| etherpadlite.env[1].name | string | `"DB_HOST"` |  |
| etherpadlite.env[1].value | string | `"moodle-etherpad-postgresql"` |  |
| etherpadlite.env[2].name | string | `"DB_PORT"` |  |
| etherpadlite.env[2].value | string | `"5432"` |  |
| etherpadlite.env[3].name | string | `"DB_NAME"` |  |
| etherpadlite.env[3].value | string | `"etherpad"` |  |
| etherpadlite.env[4].name | string | `"DB_USER"` |  |
| etherpadlite.env[4].value | string | `"etherpad"` |  |
| etherpadlite.env[5].name | string | `"DB_PASS"` |  |
| etherpadlite.env[5].valueFrom.secretKeyRef.key | string | `"etherpad-postgresql-password"` |  |
| etherpadlite.env[5].valueFrom.secretKeyRef.name | string | `"moodle"` |  |
| etherpadlite.env[6].name | string | `"REQUIRE_SESSION"` |  |
| etherpadlite.env[6].value | string | `"true"` |  |
| etherpadlite.externalDatabase.database | string | `"etherpad"` | Name of the existing database |
| etherpadlite.externalDatabase.existingSecret | string | `"moodle"` | Name of an existing secret resource containing the DB password |
| etherpadlite.externalDatabase.existingSecretKey | string | `"etherpad-postgresql-password"` | Name of the key holding the DB password in the existing Secret |
| etherpadlite.externalDatabase.host | string | `"moodle-etherpad-postgresql"` | Host of the existing database |
| etherpadlite.externalDatabase.password | string | `""` | Password for the above username |
| etherpadlite.externalDatabase.port | int | `5432` | Port of the existing database |
| etherpadlite.externalDatabase.ssl | bool | `false` | Use ssl to communicate with the database |
| etherpadlite.externalDatabase.type | string | `"postgres"` | Type of DB to provision, possible values are "postgres" |
| etherpadlite.externalDatabase.user | string | `"etherpad"` | Existing username in the external db |
| etherpadlite.image.repository | string | `"ghcr.io/dbildungsplattform/etherpad"` |  |
| etherpadlite.image.tag | string | `"2.6.1.0"` |  |
| etherpadlite.ingress.annotations."cert-manager.io/cluster-issuer" | string | `"sc-cert-manager-clusterissuer-letsencrypt"` |  |
| etherpadlite.ingress.enabled | bool | `true` |  |
| etherpadlite.ingress.hosts[0].host | string | `"etherpad.example.de"` |  |
| etherpadlite.ingress.hosts[0].paths[0].path | string | `"/"` |  |
| etherpadlite.ingress.hosts[0].paths[0].pathType | string | `"Prefix"` |  |
| etherpadlite.ingress.tls[0].hosts[0] | string | `"etherpad.example.de"` |  |
| etherpadlite.ingress.tls[0].secretName | string | `"etherpad.example.de-tls"` |  |
| etherpadlite.resources.limits.cpu | string | `"1000m"` |  |
| etherpadlite.resources.limits.memory | string | `"1Gi"` |  |
| etherpadlite.resources.requests.cpu | string | `"100m"` |  |
| etherpadlite.resources.requests.memory | string | `"128Mi"` |  |
| etherpadlite.securityContext.privileged | bool | `false` |  |
| etherpadlite.tolerations | list | `[]` |  |
| etherpadlite.volumeMounts[0].mountPath | string | `"/opt/etherpad-lite/APIKEY.txt"` |  |
| etherpadlite.volumeMounts[0].name | string | `"api-key"` |  |
| etherpadlite.volumeMounts[0].subPath | string | `"APIKEY.txt"` |  |
| etherpadlite.volumeMounts[1].mountPath | string | `"/opt/etherpad-lite/settings.json"` |  |
| etherpadlite.volumeMounts[1].name | string | `"etherpad-settings"` |  |
| etherpadlite.volumeMounts[1].subPath | string | `"settings"` |  |
| etherpadlite.volumes[0].name | string | `"api-key"` |  |
| etherpadlite.volumes[0].secret.items[0].key | string | `"etherpad-api-key"` |  |
| etherpadlite.volumes[0].secret.items[0].path | string | `"APIKEY.txt"` |  |
| etherpadlite.volumes[0].secret.secretName | string | `"moodle"` |  |
| etherpadlite.volumes[1].configMap.name | string | `"etherpad-settings"` |  |
| etherpadlite.volumes[1].name | string | `"etherpad-settings"` |  |
| global.kubectl_version | string | `"1.28.7"` |  |
| global.moodlePlugins | object | `{"adaptable":{"enabled":false},"availability_cohort":{"enabled":false},"block_stash":{"enabled":false},"board":{"enabled":false},"booking":{"enabled":false},"boost_magnific":{"enabled":false},"boost_union":{"enabled":false},"certificate":{"enabled":false},"choicegroup":{"enabled":false},"completion_progress":{"enabled":false},"coursearchiver":{"enabled":false},"coursecertificate":{"enabled":false},"customfield_dynamic":{"enabled":false},"dash":{"enabled":false},"dynamic_cohorts":{"enabled":false},"eledia_oidc":{"enabled":false},"etherpadlite":{"enabled":false},"filtercodes":{"enabled":false},"flexsections":{"enabled":false},"geogebra":{"enabled":false},"groupselect":{"enabled":false},"heartbeat":{"enabled":false},"hvp":{"enabled":false},"jitsi":{"enabled":false},"mod_checklist":{"enabled":false},"mod_subcourse":{"enabled":false},"mod_videotime":{"enabled":false},"multitopic":{"enabled":false},"oidc":{"enabled":false},"pdfannotator":{"enabled":false},"qtype_stack":{"enabled":false},"reengagement":{"enabled":false},"remuiformat":{"enabled":false},"saml2":{"enabled":false},"sharing_cart":{"enabled":false},"shortcodes":{"enabled":false},"skype":{"enabled":false},"snap":{"enabled":false},"staticpage":{"enabled":false},"tiles":{"enabled":false},"tool_mediatime":{"enabled":false},"topcoll":{"enabled":false},"unilabel":{"enabled":false},"usersuspension":{"enabled":false},"xp":{"enabled":false},"zoom":{"enabled":false}}` | All plugins are disabled by default. if enabled, the plugin is installed on image startup |
| global.security.allowInsecureImages | bool | `true` |  |
| global.storageClass | string | `"nfs-client"` | Default storage class, should support ReadWriteMany |
| moodle.affinity | object | `{}` |  |
| moodle.allowEmptyPassword | bool | `false` |  |
| moodle.containerPorts.http | int | `8080` |  |
| moodle.containerPorts.https | int | `8443` |  |
| moodle.containerSecurityContext.enabled | bool | `true` |  |
| moodle.containerSecurityContext.privileged | bool | `false` |  |
| moodle.containerSecurityContext.runAsGroup | int | `1001` |  |
| moodle.containerSecurityContext.runAsNonRoot | bool | `true` |  |
| moodle.existingSecret | string | `"moodle"` |  |
| moodle.externalDatabase.database | string | `"moodle"` | Name of the existing database |
| moodle.externalDatabase.existingSecret | string | `"moodle"` | Name of an existing secret resource containing the DB password with the key 'db-password' |
| moodle.externalDatabase.host | string | `""` | Host of the existing database |
| moodle.externalDatabase.password | string | `""` | Password for the above username |
| moodle.externalDatabase.port | int | `5432` | Port of the existing database |
| moodle.externalDatabase.type | string | `"pgsql"` | Type of DB to provision, possible values are "pgsql" |
| moodle.externalDatabase.user | string | `"moodle"` | Existing username in the external db |
| moodle.extraEnvVarsSecret | string | `""` |  |
| moodle.extraEnvVars[0].name | string | `"PHP_POST_MAX_SIZE"` |  |
| moodle.extraEnvVars[0].value | string | `"200M"` |  |
| moodle.extraEnvVars[1].name | string | `"PHP_UPLOAD_MAX_FILESIZE"` |  |
| moodle.extraEnvVars[1].value | string | `"200M"` |  |
| moodle.extraEnvVars[2].name | string | `"PHP_MAX_INPUT_VARS"` |  |
| moodle.extraEnvVars[2].value | string | `"5000"` |  |
| moodle.extraEnvVars[3].name | string | `"MOODLE_PLUGINS"` |  |
| moodle.extraEnvVars[3].valueFrom.configMapKeyRef.key | string | `"moodle-plugin-list"` |  |
| moodle.extraEnvVars[3].valueFrom.configMapKeyRef.name | string | `"moodle-plugins"` |  |
| moodle.extraEnvVars[4].name | string | `"MOODLE_PLUGINS_SYS_UNINSTALL"` |  |
| moodle.extraEnvVars[4].valueFrom.configMapKeyRef.key | string | `"moodle-plugin-sys-uninstall-list"` |  |
| moodle.extraEnvVars[4].valueFrom.configMapKeyRef.name | string | `"moodle-plugins"` |  |
| moodle.extraVolumeMounts[0].mountPath | string | `"/moodleconfig/"` |  |
| moodle.extraVolumeMounts[0].name | string | `"moodle-additional-php-ini-file"` |  |
| moodle.extraVolumeMounts[0].readOnly | bool | `true` |  |
| moodle.extraVolumeMounts[1].mountPath | string | `"/moodleconfig/config-php"` |  |
| moodle.extraVolumeMounts[1].name | string | `"moodle-php-config"` |  |
| moodle.extraVolumeMounts[1].readOnly | bool | `true` |  |
| moodle.extraVolumes[0] | object | `{"configMap":{"defaultMode":420,"items":[{"key":"moodle-php.ini","path":"01-dbp-php.ini"}],"name":"moodle-additional-php-ini-file"},"name":"moodle-additional-php-ini-file"}` | The additional php.ini which gets filled with custom values |
| moodle.extraVolumes[1] | object | `{"name":"moodle-php-config","secret":{"defaultMode":420,"items":[{"key":"config.php","path":"config.php"}],"secretName":"moodle-php-config"}}` | The custom config.php file that is used to configure moodle to use the database and redis (if activated) |
| moodle.image.debug | bool | `false` | Debug mode for more detailed moodle installation and log output |
| moodle.image.pullPolicy | string | `"Always"` |  |
| moodle.image.registry | string | `"ghcr.io"` |  |
| moodle.image.repository | string | `"dbildungsplattform/moodle"` |  |
| moodle.image.tag | string | `"4.5.12-fpm-trixie-8.2.31-dbp5"` | The dbp-moodle image which is build for this helm chart |
| moodle.ingress.annotations."cert-manager.io/cluster-issuer" | string | `"sc-cert-manager-clusterissuer-letsencrypt"` |  |
| moodle.ingress.annotations."nginx.ingress.kubernetes.io/proxy-body-size" | string | `"200M"` |  |
| moodle.ingress.annotations."nginx.ingress.kubernetes.io/proxy-connect-timeout" | string | `"30s"` |  |
| moodle.ingress.annotations."nginx.ingress.kubernetes.io/proxy-read-timeout" | string | `"20s"` |  |
| moodle.ingress.annotations."nginx.ingress.kubernetes.io/use-forwarded-headers" | string | `"true"` |  |
| moodle.ingress.annotations."nginx.ingress.kubernetes.io/whitelist-source-range" | string | `"0.0.0.0/0"` |  |
| moodle.ingress.enabled | bool | `true` |  |
| moodle.ingress.extraHosts | list | `[]` | Any additional hostnames, needs to be "name: URL" value pairs |
| moodle.ingress.hostname | string | `"example.de"` | The hostname of the moodle application |
| moodle.ingress.tls | bool | `true` |  |
| moodle.metrics.enabled | bool | `true` |  |
| moodle.metrics.image.repository | string | `"lusotycoon/apache-exporter"` |  |
| moodle.metrics.image.tag | string | `"v1.0.12"` |  |
| moodle.metrics.resources | object | `{"limits":{"cpu":"200m","memory":"256Mi"},"requests":{"cpu":"10m","memory":"16Mi"}}` | Resources have to be set so that the horizontal pod autoscaler for moodle can read the moodle cpu consumption correctly |
| moodle.metrics.service.type | string | `"ClusterIP"` |  |
| moodle.moodleEmail | string | `""` |  |
| moodle.moodleLang | string | `"de"` |  |
| moodle.moodleSiteName | string | `"Moodle"` |  |
| moodle.moodleSkipInstall | bool | `false` |  |
| moodle.moodleUsername | string | `"admin"` |  |
| moodle.networkPolicy.enabled | bool | `false` |  |
| moodle.persistence.existingClaim | string | `"moodle-data"` | If this value is unset, the bitnami/moodle chart generates its own PV & PVC |
| moodle.podAnnotations.moodle/image | string | `"{{- .Values.image.repository -}}:{{- .Values.image.tag -}}"` |  |
| moodle.podAnnotations.moodleplugins/checksum | string | `"{{- include \"dbpMoodle.pluginConfigMap.content\" . | sha256sum -}}"` |  |
| moodle.podSecurityContext.enabled | bool | `true` |  |
| moodle.readinessProbe.path | string | `"/login/index.php?noredirect=1"` |  |
| moodle.redis.enabled | string | `"{{- include \"moodle.redis.enabled\" . -}}"` |  |
| moodle.resources.limits.cpu | int | `6` |  |
| moodle.resources.limits.memory | string | `"3Gi"` |  |
| moodle.resources.requests.cpu | string | `"300m"` |  |
| moodle.resources.requests.memory | string | `"512Mi"` |  |
| moodle.service.type | string | `"ClusterIP"` |  |
| moodle.startupProbe.enabled | bool | `true` |  |
| moodle.startupProbe.failureThreshold | int | `120` |  |
| moodle.tolerations | list | `[]` |  |
| moodle.updateStrategy.type | string | `"RollingUpdate"` |  |
| moodlecronjob.affinity | object | `{}` |  |
| moodlecronjob.clusterRole.create | bool | `false` |  |
| moodlecronjob.image.repository | string | `"ghcr.io/dbildungsplattform/moodle-tools"` |  |
| moodlecronjob.image.tag | string | `"1.1.15"` |  |
| moodlecronjob.jobs[0].args[0] | string | `"/scripts/cronjob-script"` |  |
| moodlecronjob.jobs[0].backoffLimit | int | `1` |  |
| moodlecronjob.jobs[0].command[0] | string | `"/bin/bash"` |  |
| moodlecronjob.jobs[0].command[1] | string | `"-c"` |  |
| moodlecronjob.jobs[0].concurrencyPolicy | string | `"Forbid"` |  |
| moodlecronjob.jobs[0].extraVolumeMounts[0].mountPath | string | `"/scripts/"` |  |
| moodlecronjob.jobs[0].extraVolumeMounts[0].name | string | `"moodle-php-script"` |  |
| moodlecronjob.jobs[0].extraVolumes[0].configMap.defaultMode | int | `364` |  |
| moodlecronjob.jobs[0].extraVolumes[0].configMap.name | string | `"moodle-php-script"` |  |
| moodlecronjob.jobs[0].extraVolumes[0].name | string | `"moodle-php-script"` |  |
| moodlecronjob.jobs[0].failedJobsHistoryLimit | int | `1` |  |
| moodlecronjob.jobs[0].livenessProbe.exec.command[0] | string | `"cat"` |  |
| moodlecronjob.jobs[0].livenessProbe.exec.command[1] | string | `"/tmp/healthy"` |  |
| moodlecronjob.jobs[0].livenessProbe.initialDelaySeconds | int | `2` |  |
| moodlecronjob.jobs[0].livenessProbe.periodSeconds | int | `2` |  |
| moodlecronjob.jobs[0].name | string | `"php-script"` |  |
| moodlecronjob.jobs[0].restartPolicy | string | `"Never"` |  |
| moodlecronjob.jobs[0].schedule | string | `"* * * * *"` |  |
| moodlecronjob.jobs[0].successfulJobsHistoryLimit | int | `1` |  |
| moodlecronjob.podSecurityContext.fsGroup | int | `1001` |  |
| moodlecronjob.resources | object | `{}` |  |
| moodlecronjob.securityContext.allowPrivilegeEscalation | bool | `false` |  |
| moodlecronjob.securityContext.capabilities.drop[0] | string | `"ALL"` |  |
| moodlecronjob.securityContext.privileged | bool | `false` |  |
| moodlecronjob.securityContext.runAsGroup | int | `1001` |  |
| moodlecronjob.securityContext.runAsNonRoot | bool | `true` |  |
| moodlecronjob.securityContext.runAsUser | int | `1001` |  |
| moodlecronjob.serviceAccount.create | bool | `false` |  |
| moodlecronjob.serviceAccount.name | string | `"moodle-cronjob"` |  |
| moodlecronjob.tolerations | list | `[]` |  |
| postgresql.auth.database | string | `"moodle"` |  |
| postgresql.auth.existingSecret | string | `"moodle"` |  |
| postgresql.auth.secretKeys.adminPasswordKey | string | `"db-admin-password"` |  |
| postgresql.auth.secretKeys.userPasswordKey | string | `"db-password"` | Moodle expects its db password key to be db-password |
| postgresql.auth.username | string | `"moodle"` |  |
| postgresql.enabled | bool | `true` |  |
| postgresql.image.repository | string | `"bitnamilegacy/postgresql"` |  |
| postgresql.image.tag | string | `"14.18.0-debian-12-r0"` |  |
| postgresql.metrics.enabled | bool | `true` |  |
| postgresql.metrics.image.repository | string | `"bitnamilegacy/postgres-exporter"` |  |
| postgresql.metrics.serviceMonitor.enabled | bool | `true` |  |
| postgresql.primary.affinity | object | `{}` |  |
| postgresql.primary.containerSecurityContext.privileged | bool | `false` |  |
| postgresql.primary.extendedConfiguration | string | `"max_connections = 800\n"` |  |
| postgresql.primary.resources.limits.cpu | int | `9` |  |
| postgresql.primary.resources.limits.memory | string | `"3Gi"` |  |
| postgresql.primary.resources.requests.cpu | string | `"250m"` |  |
| postgresql.primary.resources.requests.memory | string | `"256Mi"` |  |
| postgresql.primary.tolerations | list | `[]` |  |
| postgresql.volumePermissions.image.repository | string | `"bitnamilegacy/os-shell"` |  |
| redis.architecture | string | `"standalone"` |  |
| redis.auth.enabled | bool | `true` |  |
| redis.auth.existingSecret | string | `"moodle"` |  |
| redis.auth.existingSecretPasswordKey | string | `"redis-password"` |  |
| redis.auth.usePasswordFileFromSecret | bool | `true` |  |
| redis.enabled | bool | `false` |  |
| redis.image.repository | string | `"bitnamilegacy/redis"` |  |
| redis.kubectl.image.repository | string | `"bitnamilegacy/kubectl"` |  |
| redis.master.affinity | object | `{}` |  |
| redis.master.resources | object | `{}` |  |
| redis.master.tolerations | list | `[]` |  |
| redis.metrics.image.repository | string | `"bitnamilegacy/redis-exporter"` |  |
| redis.sentinel.image.repository | string | `"bitnamilegacy/redis-sentinel"` |  |
| redis.sysctl.image.repository | string | `"bitnamilegacy/os-shell"` |  |
| redis.volumePermissions.image.repository | string | `"bitnamilegacy/os-shell"` |  |
| sql-exporter.affinity | object | `{}` |  |
| sql-exporter.config.collector_files[0] | string | `"collectors/sql_exporter_moodle.yaml"` |  |
| sql-exporter.config.target.collectors[0] | string | `"sql_exporter_moodle"` |  |
| sql-exporter.config.target.data_source_name | string | `""` |  |
| sql-exporter.enabled | bool | `false` |  |
| sql-exporter.extraVolumes[0].mount.mountPath | string | `"/etc/sql_exporter/collectors/"` |  |
| sql-exporter.extraVolumes[0].mount.readOnly | bool | `true` |  |
| sql-exporter.extraVolumes[0].name | string | `"moodle-collector-config"` |  |
| sql-exporter.extraVolumes[0].volume.configMap.items[0].key | string | `"moodle-collector-config"` |  |
| sql-exporter.extraVolumes[0].volume.configMap.items[0].path | string | `"sql_exporter_moodle.yaml"` |  |
| sql-exporter.extraVolumes[0].volume.configMap.name | string | `"moodle-sql-exporter-configmap"` |  |
| sql-exporter.image.pullPolicy | string | `"IfNotPresent"` |  |
| sql-exporter.resources | object | `{}` |  |
| sql-exporter.securityContext.allowPrivilegeEscalation | bool | `false` |  |
| sql-exporter.securityContext.privileged | bool | `false` |  |
| sql-exporter.tolerations | list | `[]` |  |

----------------------------------------------
Autogenerated from chart metadata using [helm-docs v1.2.0](https://github.com/norwoodj/helm-docs/releases/v1.2.0)
