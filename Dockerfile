FROM ubuntu:22.04
LABEL maintainer="ACorrêa (WMB) <artur.correa@wmnobrasil.org>"

# Prevent interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies including Python 3.11 and MariaDB dev headers
RUN apt-get update && apt-get -y install --no-install-recommends \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    gettext \
    curl \
    pkg-config \
    libmariadb-dev \
    ca-certificates \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Necessary flags for mysqlclient driver
ENV MYSQLCLIENT_CFLAGS="-I/usr/include/mariadb/"
ENV MYSQLCLIENT_LDFLAGS="-L/usr/lib/x86_64-linux-gnu/ -lmariadb"
ENV VIRTUAL_ENV=/root/www/python/venv
RUN python3.11 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV DJANGO_SETTINGS_MODULE=qsts3.settings
ENV PYTHONPATH="/root/www/python/src"

RUN pip install --upgrade pip setuptools wheel

WORKDIR /root/www/python
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
COPY translations/ ./translations/

# Install project dependencies (including dev)
RUN pip install ".[dev]"

# Verify
RUN python -c "import django; print(f'Django {django.VERSION}')"

WORKDIR /root/www/python/src
