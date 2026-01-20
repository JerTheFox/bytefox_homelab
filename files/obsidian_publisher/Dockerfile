FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y git openssh-client && \
    rm -rf /var/lib/apt/lists/*

RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g 1000 -m -s /bin/bash appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY script.py .

RUN mkdir -p /data/obsidian /app/site-repo /ssh_keys && \
    chown -R 1000:1000 /app /data /ssh_keys

USER 1000

ENV HOME=/home/appuser

CMD ["python", "-u", "script.py"]
