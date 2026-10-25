FROM internetsystemsconsortium/bind9:9.18

# named.conf chính include 2 file options/local — bắt buộc vì
# /etc/bind/named.conf mặc định của image này không tự include chúng.
COPY named.conf /etc/bind/named.conf
COPY named.conf.options /etc/bind/named.conf.options
COPY named.conf.local /etc/bind/named.conf.local
COPY db.cloud.local /etc/bind/db.cloud.local

EXPOSE 53/udp 53/tcp

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD named-checkconf || exit 1
