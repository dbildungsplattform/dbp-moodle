#!/bin/bash
curl https://pecl.php.net/get/redis-6.3.0.tgz --output /tmp/redis-6.3.0.tgz
cd /tmp
tar xzf /tmp/redis-6.3.0.tgz
rm /tmp/redis-6.3.0.tgz
cd /tmp/redis-6.3.0
phpize
./configure
make
make install