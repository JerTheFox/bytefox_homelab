#!/bin/sh

# 1. Генерация сертификатов
if [ ! -f /etc/ocserv/server-cert.pem ]; then
    echo "Generating certificates..."
    cd /etc/ocserv

    # Шаблон CA
    cat <<EOF > ca.tmpl
cn = "VPN CA"
organization = "ByteFox Lab"
serial = 1
expiration_days = 3650
ca
signing_key
cert_signing_key
crl_signing_key
EOF

    # Шаблон Сервера
    cat <<EOF > server.tmpl
cn = "vpn.bytefox.ru"
organization = "ByteFox Lab"
serial = 2
expiration_days = 3650
encryption_key
signing_key
tls_www_server
ip_address = "192.168.1.10"
EOF

    # Генерация ключей
    certtool --generate-privkey --outfile ca-key.pem
    certtool --generate-self-signed --load-privkey ca-key.pem --template ca.tmpl --outfile ca-cert.pem
    certtool --generate-privkey --outfile server-key.pem
    certtool --generate-certificate --load-privkey server-key.pem --load-ca-certificate ca-cert.pem --load-ca-privkey ca-key.pem --template server.tmpl --outfile server-cert.pem

    # Удаляем шаблоны
    rm ca.tmpl server.tmpl
fi

# 2. Создание файла пользователей
if [ ! -f /etc/ocserv/ocpasswd ]; then
    touch /etc/ocserv/ocpasswd
fi

# 3. Настройка NAT
iptables -t nat -A POSTROUTING -j MASQUERADE

# 4. Включение Forwarding
echo 1 > /proc/sys/net/ipv4/ip_forward

# 5. Запуск сервера
echo "Starting OpenConnect Server..."
exec ocserv -c /etc/ocserv/ocserv.conf -f
