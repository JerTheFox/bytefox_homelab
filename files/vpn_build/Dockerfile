FROM debian:bookworm-slim

# gnutls-bin содержит certtool
RUN apt-get update && \
    apt-get install -y ocserv iptables gnutls-bin && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /etc/ocserv

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
