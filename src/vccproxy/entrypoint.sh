#!/bin/sh

htpasswd -bc /usr/local/apache2/conf/.htpasswd ${VCC_USERNAME} ${VCC_PASSWORD}

if [ \"$VCC_PROXY_SSL_ACTIVE\" = \"true\"]; then
    echo 'Include /usr/local/apache2/conf/extra/httpd-vcc-proxy-ssl.conf' >> /usr/local/apache2/conf/httpd.conf
else
    echo 'Include /usr/local/apache2/conf/extra/httpd-vcc-proxy.conf' >> /usr/local/apache2/conf/httpd.conf
fi

httpd-foreground