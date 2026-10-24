# Authentication & Identity Server (Keycloak) — Tài liệu đầy đủ

## 1. Vai trò trong hệ thống

`authentication-identity-server` là **Identity Provider (IdP)** của MyMiniCloud, chạy **Keycloak**. Nhiệm vụ:

- Quản lý Realm, Client, User theo chuẩn OIDC (OpenID Connect, xây trên nền OAuth2).
- Phát hành **Access Token (JWT, RS256)** khi user đăng nhập thành công.
- Cung cấp **JWKS** (JSON Web Key Set — tập public key) để các service khác (ở đây là `application-backend-server`) tự xác minh chữ ký token mà không cần gọi lại Keycloak mỗi request.

Service duy nhất tiêu thụ token do server này phát hành (hiện tại) là endpoint `GET /secure` của `application-backend-server`.

## 2. Công nghệ & vị trí trong hạ tầng

| Thuộc tính | Giá trị |
|---|---|
| Image | `quay.io/keycloak/keycloak:26.4.0` (đã pin version, không dùng `:latest`) |
| Container name | `authentication-identity-server` |
| Chế độ chạy | `start-dev` — **chỉ dành cho demo/lab**, không phải cấu hình production |
| Network | `cloud-net` (Docker bridge network dùng chung toàn hệ thống) |
| Cổng container | `8080` |
| Cổng host | `8081` |
| Volume bền vững | `keycloak_data:/opt/keycloak/data` |

## 3. Cấu trúc thư mục

```
authentication-identity-server/
├── docs/
│   └── README.md                # (file này) toàn bộ thông tin của service
├── plan.md                      # kế hoạch triển khai + log chi tiết các bước đã thực thi
└── realm-export.json            # định nghĩa Realm/Client/User, tự import khi container khởi động
```

## 4. Cấu hình đầy đủ trong `docker-compose.yml`

```yaml
volumes:
  keycloak_data:

services:
  authentication-identity-server:
    image: quay.io/keycloak/keycloak:26.4.0
    container_name: authentication-identity-server
    command: ["start-dev", "--import-realm"]
    environment:
      KC_BOOTSTRAP_ADMIN_USERNAME: admin
      KC_BOOTSTRAP_ADMIN_PASSWORD: admin
      KC_HOSTNAME_STRICT: "false"
      KC_HTTP_ENABLED: "true"
    ports:
      - "8081:8080"
    volumes:
      - keycloak_data:/opt/keycloak/data
      - ./authentication-identity-server/realm-export.json:/opt/keycloak/data/import/realm-export.json:ro
    networks:
      - cloud-net
    restart: unless-stopped
```

Giải thích từng phần:

- `command: ["start-dev", "--import-realm"]` — chạy Keycloak ở dev mode (không cần cấu hình TLS/production), đồng thời tự động import mọi file JSON đặt trong `/opt/keycloak/data/import/` khi container khởi động.
- `KC_BOOTSTRAP_ADMIN_USERNAME/PASSWORD: admin/admin` — tài khoản quản trị Keycloak, chỉ dùng cho demo.
- `KC_HOSTNAME_STRICT: "false"` — không ép Keycloak dùng một hostname cố định; Keycloak tự suy ra hostname từ request đến (xem mục 6 — lý do kỹ thuật quan trọng nhất).
- `KC_HTTP_ENABLED: "true"` — cho phép truy cập qua HTTP thuần (dev mode), vì không có chứng chỉ TLS trong lab này.
- `keycloak_data:/opt/keycloak/data` — volume bền vững, giữ toàn bộ dữ liệu Keycloak (Realm, Client, User, session...) qua các lần container bị recreate. Trước khi thêm volume này, mọi dữ liệu bị mất mỗi khi container được tạo lại.
- Mount `realm-export.json` (read-only) vào thư mục import — nguồn dữ liệu để tự provision Realm/Client/User.

## 5. Nội dung `realm-export.json` (định nghĩa Realm/Client/User)

```json
{
  "realm": "realm_nhom13",
  "enabled": true,
  "sslRequired": "none",
  "registrationAllowed": false,
  "accessTokenLifespan": 1800,
  "clients": [
    {
      "clientId": "flask-app",
      "name": "MyMiniCloud Flask App",
      "enabled": true,
      "protocol": "openid-connect",
      "publicClient": true,
      "standardFlowEnabled": true,
      "directAccessGrantsEnabled": true,
      "serviceAccountsEnabled": false,
      "redirectUris": ["http://localhost/*", "http://localhost:8085/*"],
      "webOrigins": ["+"],
      "protocolMappers": [
        {
          "name": "flask-app-audience",
          "protocol": "openid-connect",
          "protocolMapper": "oidc-audience-mapper",
          "consentRequired": false,
          "config": {
            "included.client.audience": "flask-app",
            "id.token.claim": "false",
            "access.token.claim": "true"
          }
        }
      ]
    }
  ],
  "users": [
    {
      "username": "sv01",
      "enabled": true,
      "emailVerified": true,
      "requiredActions": [],
      "firstName": "Sinh",
      "lastName": "Vien01",
      "credentials": [{"type": "password", "value": "Sv01Demo@123!", "temporary": false}],
      "realmRoles": ["default-roles-realm_nhom13"]
    }
  ]
}
```

### Giải thích từng trường quan trọng

| Trường | Ý nghĩa |
|---|---|
| `realm: "realm_nhom13"` | Tên Realm — một không gian cách ly hoàn toàn (user, client, role riêng) trong Keycloak |
| `accessTokenLifespan: 1800` | Access Token sống 1800 giây (30 phút) trước khi hết hạn (`exp`) |
| `clientId: "flask-app"` | Định danh client mà `application-backend-server` dùng để kiểm tra claim `aud` trong token |
| `publicClient: true` | Client **không có** `client_secret` — phù hợp cho app không thể giữ secret an toàn (ví dụ SPA, hoặc trong lab này dùng password grant trực tiếp từ `curl`) |
| `standardFlowEnabled: true` | Cho phép Authorization Code flow (chuẩn OIDC cho web app) |
| `directAccessGrantsEnabled: true` | Cho phép **Resource Owner Password Credentials grant** — lấy token trực tiếp bằng username/password qua API, không qua trình duyệt. Chỉ nên dùng cho demo/lab, không khuyến nghị cho production vì client phải cầm password người dùng |
| `serviceAccountsEnabled: false` | Không bật client credentials grant (không cần service-to-service auth trong lab này) |
| `redirectUris` | Danh sách URL được phép redirect về sau khi login qua Authorization Code flow |
| `protocolMappers` → `oidc-audience-mapper` | Mapper gắn thêm giá trị `flask-app` vào claim `aud` của Access Token. **Bắt buộc phải có** vì Flask kiểm tra chính xác `audience="flask-app"` |
| `username: "sv01"`, `credentials` | User demo và mật khẩu khai báo trong file — **nhưng xem mục 8, mật khẩu này không được Keycloak áp dụng khi import** |

## 6. Vì sao KHÔNG set `KC_HOSTNAME` — điểm kỹ thuật quan trọng nhất

Đây là quyết định thiết kế cốt lõi của service này, nên hiểu rõ trước khi thay đổi bất kỳ cấu hình nào.

`application-backend-server` chạy **trong** cùng network Docker (`cloud-net`) và gọi Keycloak bằng **hostname nội bộ** `authentication-identity-server:8080` để:
1. Tải JWKS (public key để verify chữ ký JWT).
2. Kiểm tra claim `iss` (issuer) trong token có khớp với `OIDC_ISSUER` đã cấu hình hay không.

Nếu set `KC_HOSTNAME=http://localhost:8081` (như cách làm trực quan ban đầu), Keycloak sẽ phát hành token với:
```
"iss": "http://localhost:8081/realms/realm_nhom13"
```
Nhưng Flask xác minh issuer theo:
```
OIDC_ISSUER = "http://authentication-identity-server:8080/realms/realm_nhom13"
```
Hai giá trị **không khớp** → mọi token hợp lệ về chữ ký vẫn bị Flask từ chối với lỗi 401, vì issuer sai.

**Giải pháp đang áp dụng:**
- Không set `KC_HOSTNAME`.
- Set `KC_HOSTNAME_STRICT: "false"` → Keycloak tự suy ra hostname dựa theo request đến (feature "dynamic hostname" của Keycloak ở dev mode).

Hệ quả thực tế:
- Khi gọi từ **máy host** (ví dụ dùng `curl` hoặc mở Admin Console trên trình duyệt máy mình) → dùng `http://localhost:8081/...` → Keycloak trả về `iss` dùng `localhost:8081`.
- Khi `application-backend-server` gọi **từ trong container khác** → dùng `http://authentication-identity-server:8080/...` → Keycloak trả về `iss` dùng `authentication-identity-server:8080`.

Cả hai cách đều trỏ tới **cùng một Keycloak instance**, chỉ khác giá trị `iss`/base URL tùy theo góc nhìn mạng của người gọi. Vì vậy, **khi lấy token để test với Flask, phải lấy token bằng đúng route mà Flask cũng dùng để verify issuer** — nếu lấy token qua `localhost:8081` rồi đưa cho Flask verify theo `authentication-identity-server:8080`, token sẽ luôn bị từ chối do issuer lệch. Trong thực tế test đã làm, lệnh `curl` lấy token từ máy host (`localhost:8081`) sẽ cho ra token với issuer `localhost:8081`, không dùng để test `/secure` được — phải gọi lấy token **từ trong một container khác** (ví dụ `docker exec application-backend-server ...`) để issuer khớp đúng `authentication-identity-server:8080`.

## 7. Luồng hoạt động chi tiết

### 7.1. Luồng provisioning — khi container khởi động lần đầu (volume trống)

```
docker compose up -d authentication-identity-server
        │
        ▼
Keycloak chạy "start-dev --import-realm"
        │
        ▼
Đọc toàn bộ file JSON trong /opt/keycloak/data/import/
   (ở đây chỉ có realm-export.json)
        │
        ▼
Tạo Realm "realm_nhom13" (vì chưa tồn tại)
        │
        ▼
Tạo Client "flask-app" (public, standard flow + direct access grants)
        │
        ▼
Gắn Protocol Mapper "flask-app-audience" vào Client
        │
        ▼
Tạo User "sv01" (role default-roles-realm_nhom13)
        │
        ▼
[VẤN ĐỀ] Mật khẩu khai báo trong "credentials" KHÔNG được áp dụng
        │
        ▼
Log: "Realm 'realm_nhom13' imported" + "Import finished successfully"
        │
        ▼
Keycloak lắng nghe tại :8080, sẵn sàng nhận request OIDC
```

### 7.2. Luồng lấy Access Token (Resource Owner Password Credentials Grant)

```
Client ──POST──▶ {issuer}/protocol/openid-connect/token
                 Body (form-urlencoded):
                   client_id=flask-app
                   grant_type=password
                   username=sv01
                   password=Sv01Demo@123!
        │
        ▼
Keycloak kiểm tra: Client tồn tại & enabled, direct access grants bật,
                    User tồn tại & enabled & mật khẩu khớp & không bị
                    chặn bởi required action nào
        │
        ├─ Sai → 400 {"error": "invalid_grant", "error_description": "..."}
        │
        ▼ (đúng)
200 OK:
{
  "access_token": "<JWT RS256>",
  "expires_in": 1800,
  "refresh_token": "<JWT>",
  "refresh_expires_in": 1800,
  "token_type": "Bearer",
  "scope": "email profile"
}
```

Payload (decode) của Access Token mẫu thực tế đã lấy được:

```json
{
  "exp": 1792779616,
  "iat": 1792777816,
  "iss": "http://authentication-identity-server:8080/realms/realm_nhom13",
  "aud": ["flask-app", "account"],
  "sub": "d6e040b7-d047-47f8-8a67-dff4ce86199f",
  "typ": "Bearer",
  "azp": "flask-app",
  "realm_access": {
    "roles": ["offline_access", "uma_authorization", "default-roles-realm_nhom13"]
  },
  "preferred_username": "sv01",
  "email": "sv01@minicloud.local",
  "given_name": "Sinh",
  "family_name": "Vien01"
}
```

### 7.3. Luồng xác minh token ở phía `application-backend-server`

(Chi tiết đầy đủ nằm trong code `application-backend-server/app.py`, tóm tắt lại đây vì đây là phía "tiêu thụ" trực tiếp dữ liệu do Keycloak phát hành.)

```
Client ──GET /secure, Authorization: Bearer <token>──▶ application-backend-server
        │
        ▼
1. Lấy "kid" từ header JWT (chưa verify chữ ký)
        │
        ▼
2. Tra cứu "kid" trong JWKS cache (cache theo tiến trình, TTL 600s)
        │   - Cache hết hạn hoặc chưa có → GET {issuer}/protocol/openid-connect/certs
        │   - Lỗi mạng/HTTP/JSON khi gọi Keycloak → raise IdentityUnavailable
        │   - Không tìm thấy "kid" khớp sau khi refresh 1 lần → JWTError
        ▼
3. jwt.decode(token, key, algorithms=["RS256"],
              issuer=OIDC_ISSUER, audience=OIDC_AUDIENCE,
              options={require_exp, require_iss, require_aud})
        │
        ├─ IdentityUnavailable (Keycloak không truy cập được) → 503
        ├─ JWTError (sai chữ ký/issuer/audience/hết hạn)      → 401
        └─ Hợp lệ → 200 {"message": "...", "preferred_username": "sv01"}
```

JWKS endpoint cụ thể đang dùng:
```
http://authentication-identity-server:8080/realms/realm_nhom13/protocol/openid-connect/certs
```

## 8. Vấn đề đã gặp trong thực tế và cách khắc phục

### 8.1. Mật khẩu User không được áp dụng khi import Realm

**Hiện tượng:** Sau khi Keycloak import `realm-export.json` thành công (user `sv01` xuất hiện, enabled = true), gọi token endpoint với đúng username/password khai báo trong file vẫn bị lỗi:

```json
{"error": "invalid_grant", "error_description": "Account is not fully set up"}
```

Kiểm tra qua Admin API cho thấy `disableableCredentialTypes` của user rỗng — nghĩa là Keycloak tạo user nhưng không lưu credential `password` từ trường `credentials` trong file export, dù định dạng JSON đúng cú pháp chuẩn của Keycloak.

**Cách khắc phục đã áp dụng:** set lại mật khẩu bằng Keycloak Admin REST API ngay sau khi container khởi động lần đầu:

```bash
# 1. Lấy Admin Access Token (realm master, client admin-cli có sẵn)
ADMIN_TOKEN=$(curl -s -X POST \
  http://localhost:8081/realms/master/protocol/openid-connect/token \
  -d "client_id=admin-cli" \
  -d "grant_type=password" \
  -d "username=admin" \
  -d "password=admin" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. Tìm User ID của sv01 trong realm_nhom13
USER_ID=$(curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  "http://localhost:8081/admin/realms/realm_nhom13/users?username=sv01" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")

# 3. Set lại mật khẩu, không tạm thời (không bắt đổi password lần đăng nhập đầu)
curl -s -X PUT -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  "http://localhost:8081/admin/realms/realm_nhom13/users/$USER_ID/reset-password" \
  -d '{"type":"password","value":"Sv01Demo@123!","temporary":false}'
```

Sau bước này, `curl` lấy token thành công (HTTP 200).

> **Việc này cần làm lại mỗi khi dựng Keycloak từ một volume mới** (ví dụ sau `docker volume rm nhom13minicloud_keycloak_data`). Nên viết thành script `seed-users.sh` đóng gói 3 bước trên để nhóm dùng lại nhanh — hiện chưa có script này, vẫn đang chạy tay.

### 8.2. User cần có email hợp lệ

Realm mặc định của Keycloak có các required action ngầm (`VERIFY_EMAIL`, `UPDATE_PROFILE`...) có thể chặn user chưa có email. Đã thêm vào cấu hình user qua Admin API:

```bash
curl -s -X PUT -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  "http://localhost:8081/admin/realms/realm_nhom13/users/$USER_ID" \
  -d '{"email":"sv01@minicloud.local","emailVerified":true}'
```

### 8.3. JWKS cache che lấp việc Keycloak bị tắt

Khi test tắt Keycloak (`docker compose stop authentication-identity-server`) để kiểm tra case lỗi 503, gọi `/secure` với token cũ **vẫn trả 200** thay vì 503. Nguyên nhân: Flask đã cache JWKS (TTL 600s) từ trước khi Keycloak bị tắt, nên không cần gọi lại Keycloak để verify token đó. Đây **không phải lỗi**, mà là hành vi thiết kế đúng của cơ chế cache — đánh đổi giữa độ sẵn sàng (vẫn phục vụ được dù IdP tạm gián đoạn) và việc phát hiện tức thời khi IdP down. Để demo đúng case 503, cần đảm bảo Flask **chưa từng load JWKS** trước khi tắt Keycloak (ví dụ: tắt Keycloak → restart `application-backend-server` → gọi `/secure`).

## 9. Kết quả kiểm thử thực tế (đã xác nhận hoạt động)

| # | Test case | Cách test | Kết quả |
|---|---|---|---|
| 1 | Container khởi động, tự import Realm | Đọc log container | ✅ `Realm 'realm_nhom13' imported`, `Import finished successfully` |
| 2 | Xoá volume, dựng lại từ đầu | `docker compose rm -f` + `docker volume rm` + `up -d` | ✅ Realm/Client tự tạo lại đúng nhờ `--import-realm` |
| 3 | Lấy Access Token đúng user/pass | `curl POST .../token` (gọi từ trong container để issuer khớp) | ✅ HTTP 200, có `access_token`, `expires_in=1800` |
| 4 | Decode JWT kiểm tra claim | Giải mã payload JWT | ✅ `iss` khớp `OIDC_ISSUER` của Flask, `aud` chứa `flask-app` |
| 5 | `GET /secure` không có token | `curl` không header Authorization | ✅ 401 |
| 6 | `GET /secure` token sai (`garbage.token.here`) | `curl -H "Authorization: Bearer garbage.token.here"` | ✅ 401 |
| 7 | `GET /secure` token hợp lệ | `curl` kèm token thật | ✅ 200, `preferred_username: "sv01"` |
| 8 | Gọi `/secure` qua API Gateway (`/api/secure`) | `curl http://localhost/api/secure` | ✅ Hành vi giống gọi trực tiếp backend |
| 9 | Tắt Keycloak, gọi lại `/secure` với token cũ | `docker compose stop` rồi `curl` | ⚠️ Trả 200 do JWKS đã cache trước đó (xem mục 8.3) — chưa test đúng điều kiện trigger 503 |

**Chưa test:**
- Token hết hạn (`exp` ở quá khứ) — khó test nhanh vì access token sống 1800s theo mặc định; có thể giảm `accessTokenLifespan` tạm thời để demo.
- Sai mật khẩu / sai client khi lấy token (dự kiến Keycloak trả `invalid_grant` theo đúng chuẩn OIDC, nhưng chưa xác nhận bằng test thực tế).
- Case 503 đúng điều kiện (JWKS chưa từng cache khi Keycloak bị tắt).

## 10. Thông số kết nối tóm tắt (tra cứu nhanh)

| Hạng mục | Giá trị |
|---|---|
| Realm | `realm_nhom13` |
| Client ID | `flask-app` (public, không có secret) |
| Audience JWT | `flask-app` |
| Issuer (Flask kiểm tra) | `http://authentication-identity-server:8080/realms/realm_nhom13` |
| Token endpoint | `{issuer}/protocol/openid-connect/token` |
| JWKS endpoint | `{issuer}/protocol/openid-connect/certs` |
| User demo | `sv01` / `Sv01Demo@123!` (phải set lại qua Admin API sau khi import, xem mục 8.1) |
| Admin Console | `http://localhost:8081` (`admin` / `admin`) |
| Thuật toán JWT | RS256 |
| Access Token TTL | 1800 giây (30 phút) |
| Cổng truy cập từ host | `8081` → container `8080` |
| Qua API Gateway | `http://localhost/auth/...` (forward nguyên vẹn sang Keycloak) |

## 11. Những gì còn thiếu / rủi ro cần xử lý trước khi coi là "xong"

| Mục | Mức độ | Mô tả |
|---|---|---|
| Mật khẩu admin mặc định | Cao | `admin/admin` — cần đổi và đưa vào biến môi trường/`.env` không commit Git trước khi public hoặc deploy EC2 |
| Mật khẩu demo trong `realm-export.json` | Trung bình | File chứa `Sv01Demo@123!` dạng plaintext trong `credentials` (dù Keycloak không áp dụng được giá trị này) — nên loại bỏ khỏi file commit Git, luôn set qua script Admin API riêng |
| `start-dev` không phải production | Cao (về mặt kiến trúc) | Không HTTPS, không DB chuyên dụng bền vững cho Keycloak ngoài volume `keycloak_data` (Keycloak dev mode dùng H2 embedded) |
| Script seed mật khẩu user chưa tự động hoá | Trung bình | Hiện phải chạy tay 3 lệnh `curl` (mục 8.1) sau mỗi lần dựng từ volume mới |
| Chưa test case 503 đúng điều kiện | Thấp | Cần quy trình test riêng, tắt Keycloak trước khi JWKS từng được cache |
| Chưa test token hết hạn | Thấp | Access token TTL mặc định dài (1800s), khó test nhanh nếu không chỉnh tạm `accessTokenLifespan` |
| Chưa triển khai AWS EC2 | Cao (yêu cầu dự án) | Toàn bộ kiểm thử ở trên mới chạy trên local |
| Route `/auth/` qua Gateway forward toàn bộ | Trung bình | Bao gồm cả path Admin Console (`/auth/admin/...`) — nếu Gateway public thật, nên giới hạn chỉ forward path cần thiết (`/auth/realms/...`), tránh lộ trang quản trị Keycloak ra ngoài |

## 12. Tài liệu liên quan

- `authentication-identity-server/plan.md` — kế hoạch triển khai gốc, checklist theo từng giai đoạn (A–G), lịch sử cập nhật tiến độ.
- `docs/04-authentication-identity.md` (ở gốc repo) — bản tóm tắt ngắn hơn trong tài liệu tổng quan toàn hệ thống.
- `docs/02-application-backend.md` — chi tiết phía tiêu thụ token (`application-backend-server`), bao gồm toàn bộ logic verify JWT.
- `docs/08-api-gateway.md` — cách route `/auth/` được forward qua API Gateway.
