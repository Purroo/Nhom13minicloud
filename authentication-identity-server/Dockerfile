FROM quay.io/keycloak/keycloak:26.4.0

# Realm/Client/User được provision tự động khi Keycloak khởi động, nhờ
# --import-realm quét các file JSON trong thư mục import mặc định.
COPY realm-export.json /opt/keycloak/data/import/realm-export.json

# Cố định hostname để claim "iss" của token luôn là
# http://authentication-identity-server:8080/realms/realm_nhom13,
# bất kể client gọi qua localhost:8081 (Postman/trình duyệt) hay qua tên
# service nội bộ. Nhờ đó application-backend-server (OIDC_ISSUER) luôn khớp.
ENV KC_HOSTNAME=http://authentication-identity-server:8080
# Admin Console vẫn truy cập được từ máy host qua localhost:8081.
ENV KC_HOSTNAME_ADMIN=http://localhost:8081

# Biến môi trường admin bootstrap (chỉ dùng cho demo local, không dùng
# cho production) được đặt ở docker-compose.yml, không hardcode ở đây.

EXPOSE 8080

ENTRYPOINT ["/opt/keycloak/bin/kc.sh"]
CMD ["start-dev", "--import-realm"]
