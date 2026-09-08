FROM php:8.2.31-fpm-trixie AS build
USER root
ARG MOODLE_VERSION=${MOODLE_VERSION:-"4.5.12"}
#This is the path moodle will be placed after downloading for our Moodle Update Pipeline
ARG MOODLE_PATH="/opt/dbp-moodle/moodle"
ARG EXTRA_LOCALES=""
#At the moment Apache will be updated to the latest release as unattended update during the build process
ARG APACHE_VERSION=${APACHE_VERSION:-"2.4.67-1~deb13u1"}
ARG APACHE_DOWNLOAD_URL="https://snapshot.debian.org/archive/debian/20260508T024741Z/pool/main/a/apache2"
WORKDIR /
ARG WITH_ALL_LOCALES="no"
RUN mkdir /bitnami
RUN mkdir /dbp-moodle

COPY scripts/install /scripts/install
COPY scripts/init /scripts/init
COPY libraries /scripts

#Add user with ID 1001
RUN useradd moodle -u 1001

RUN chmod -R +x /scripts/

# Redis is the php extension php-redis required to connect to the redis session store
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y wget gpg curl acl gnupg jq ca-certificates cron locales git unzip zip autoconf && \
    pecl install redis && \ 
    docker-php-ext-enable redis

# Install psql Version 13.x like in the other bitnami moodle image
RUN curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/postgresql.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/postgresql.gpg] https://apt.postgresql.org/pub/repos/apt trixie-pgdg main" > /etc/apt/sources.list.d/pgdg.list

RUN apt-get update && \
    apt-get install -y postgresql-client-13

# Install apache2 and its dependencies
RUN apt-get install -y libapr1 libaprutil1 libc6 libaprutil1-dbd-sqlite3 libcurl4 libaprutil1-ldap libexpat1 liblua5.3-0 libssl3 libxml2 media-types procps
RUN curl -LO ${APACHE_DOWNLOAD_URL}/apache2-bin_${APACHE_VERSION}_amd64.deb && \
    curl -LO ${APACHE_DOWNLOAD_URL}/apache2-data_${APACHE_VERSION}_all.deb && \
    curl -LO ${APACHE_DOWNLOAD_URL}/apache2-utils_${APACHE_VERSION}_amd64.deb && \
    curl -LO ${APACHE_DOWNLOAD_URL}/apache2_${APACHE_VERSION}_amd64.deb && \
    dpkg -i *.deb || apt-get -y -f install && \
    apt-get install -y libapache2-mod-fcgid && \
    rm *.deb

#Install other dependencies

RUN apt-get update && \
    apt-get install -y nano gettext imagemagick libmemcached11 libpq5 libzip-dev libxml2 libxslt1.1 && \
    rm -rf /var/lib/apt/lists/*

RUN /scripts/init/phpRedisInstall.sh

# Install Composer globally (Required for the Moosh installation)
RUN curl -sS https://getcomposer.org/installer | php -- \
    --install-dir=/usr/local/bin --filename=composer

# Install moosh for plugin management
# Because of current problems with moosh and no new release we use commit hashes. This one is the version bump to 1.38
RUN curl -L https://github.com/tmuras/moosh/archive/c7674a7b8de77a3205a289c89bed093377a20004.tar.gz -o moosh.tar.gz && \
    mkdir /moosh && tar -xzvf moosh.tar.gz -C /moosh/ --strip-components=1
RUN mkdir /.moosh &&\
    chmod 774 /.moosh &&\
    cd /moosh/ && \
    composer install && \
    ln -s /moosh/moosh.php /usr/local/bin/moosh

RUN /scripts/install/downloadMoodle.sh

RUN MAJOR_MINOR=$(echo "$MOODLE_VERSION" | cut -d. -f1,2) && \
    curl -L https://download.moodle.org/download.php/direct/langpack/${MAJOR_MINOR}/de.zip --output /tmp/de.zip && \
    curl -L https://download.moodle.org/download.php/direct/langpack/${MAJOR_MINOR}/en.zip --output /tmp/en.zip

# Hardening
RUN apt-get update && apt-get upgrade -y && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*
RUN find / -perm /6000 -type f -exec chmod a-s {} \; || true
RUN sed -i -e '/pam_loginuid.so/ s/^#*/#/' /etc/pam.d/cron

RUN update-locale LANG=C.UTF-8 LC_MESSAGES=POSIX && \
    DEBIAN_FRONTEND=noninteractive dpkg-reconfigure locales && \
    echo 'en_US.UTF-8 UTF-8' >> /etc/locale.gen
RUN echo 'en_AU.UTF-8 UTF-8' >> /etc/locale.gen
RUN echo 'de_DE.UTF-8 UTF-8' >> /etc/locale.gen
RUN /scripts/install/generate-locales.sh

RUN chmod +x /scripts/install/generate-locales.sh && \
    /scripts/install/generate-locales.sh

COPY /scripts/init/apache/httpd.conf /etc/apache2/apache2.conf

RUN /scripts/install/apacheInstall.sh

# Php configuration and installation
RUN /scripts/install/phpInstall.sh

# Prepare Moodle
RUN chmod -R g+w /etc/apache2/
RUN /scripts/install/moodleInstall.sh

EXPOSE 8080 8443

# Install plugins to the image
RUN mkdir /plugins && /scripts/install/downloadPlugins.sh

RUN apt-get remove -y curl && \
    apt-get autoremove -y

RUN chmod -R g+w /opt/dbp-moodle
RUN chown 1001:1001 -R /opt/dbp-moodle

RUN chmod -R g+w /dbp-moodle
RUN chown 1001:1001 -R /dbp-moodle

RUN chown 1001:root -R /scripts
RUN chown 1001:root -R /plugins

RUN chown 1001:1001 -R /var/log/apache2
RUN chown 1001:1001 -R /etc/apache2
RUN chown 1001:1001 -R /usr/local/etc/php

USER 1001

ENTRYPOINT ["/scripts/init/entrypoint.sh"]
