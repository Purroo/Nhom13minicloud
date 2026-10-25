FROM quay.io/keycloak/keycloak:26.4.0

# Realm/Client/User được provision tự động khi Keycloak khởi động, nhờ
# --import-realm quét các file JSON trong thư mục import mặc định.
COPY realm-export.json /opt/keycloak/data/import/realm-export.json

# Không đặt KC_HOSTNAME: Keycloak suy ra hostname từ request (KC_HOSTNAME_STRICT=false
# trong docker-compose.yml). Nếu cố định sang tên service nội bộ, trình duyệt sẽ bị
# chuyển tới http://authentication-identity-server:8080 (không phân giải được từ máy
# host) và Admin Console không đăng nhập được. Claim "iss" nhiều dạng được
# application-backend-server chấp nhận qua OIDC_ISSUER_ALIASES / ISSUER_HOST_ALLOWLIST.

# Biến môi trường admin bootstrap (chỉ dùng cho demo local, không dùng
# cho production) được đặt ở docker-compose.yml, không hardcode ở đây.

EXPOSE 8080

ENTRYPOINT ["/opt/keycloak/bin/kc.sh"]
CMD ["start-dev", "--import-realm"]
