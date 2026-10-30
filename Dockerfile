FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-client \
    sshpass \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt* ./
RUN pip install --no-cache-dir requests rich paramiko || pip install --no-cache-dir requests rich

COPY tuibox_latest /app/tuibox_latest

RUN mkdir -p /var/log/tuibox

CMD ["python3", "/app/tuibox_latest"]
