FROM docker-registry.tools.wmflabs.org/toolforge-python311-sssd-web:latest
LABEL maintainer="ACorrêa (WMB) <artur.correa@wmnobrasil.org>"

# Install system dependencies
RUN apt-get update && apt-get -y install gettext curl

# Necessary flags for mysqlclient driver
ENV MYSQLCLIENT_CFLAGS="-I/usr/include/mariadb/"
ENV MYSQLCLIENT_LDFLAGS="-L/usr/lib/x86_64-linux-gnu/ -lmariadb"
ENV VIRTUAL_ENV /root/www/python/venv
ENV PATH="/root/www/python/venv/bin:${PATH}"
ENV DJANGO_SETTINGS_MODULE=qsts3.settings
ENV PYTHONPATH="/root/www/python/src:${PYTHONPATH}"

# Bootstrap like in Toolforge, then install dependencies, including dev dependencies
WORKDIR /root/www/python/src/
COPY pyproject.toml README.md LICENSE /root/www/python/
RUN webservice-python-bootstrap && pip install "/root/www/python[dev]"
