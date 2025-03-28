FROM docker-registry.tools.wmflabs.org/toolforge-python311-sssd-web:latest AS builder
LABEL maintainer="Miguel Galves <mgalves@gmail.com>"

# Install system dependencies
RUN apt-get update && apt-get -y install sudo gettext

# Creating our local user and group
RUN adduser --disabled-password --home /home/wmb --shell /bin/bash wmb && \
    adduser wmb sudo

# We dont want any password when running SUDO
RUN echo '%sudo ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

# changing to our local user
USER wmb
RUN mkdir -p /home/wmb/www/python/src /home/wmb/www/python/static

# Necessary flags for mysqlclient driver
ENV MYSQLCLIENT_CFLAGS="-I/usr/include/mariadb/" \
    MYSQLCLIENT_LDFLAGS="-L/usr/lib/x86_64-linux-gnu/ -lmariadb"

COPY src/requirements.txt /home/wmb/www/python/src
RUN sudo chown wmb:wmb /home/wmb/www/python/src/requirements.txt

ENV VIRTUAL_ENV /home/wmb/www/python/venv
ENV PATH="/home/wmb/www/python/venv/bin:${PATH}"
ENV DJANGO_SETTINGS_MODULE=qsts3.settings
ENV PYTHONPATH="/home/wmb/www/python/src:${PYTHONPATH}"

WORKDIR /home/wmb/www/python/src/

RUN webservice-python-bootstrap

FROM builder AS development

COPY requirements-dev.txt /home/wmb/www/python/
RUN sudo chown wmb:wmb /home/wmb/www/python/requirements-dev.txt
RUN pip install -r /home/wmb/www/python/requirements-dev.txt

COPY pytest.ini /home/wmb/www/python/
RUN sudo chown wmb:wmb /home/wmb/www/python/pytest.ini
