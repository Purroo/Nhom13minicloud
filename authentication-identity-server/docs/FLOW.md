# Luồng xử lý request tại Authentication & Identity Server

Tài liệu này tập trung vào **3 câu hỏi**: ai gọi tới `authentication-identity-server`, gọi qua đường nào, và bên trong Keycloak xử lý request đó như thế nào. Thông tin kiến trúc tổng quát (cổng, volume, Realm/Client) đã có ở `README.md` cùng thư mục — file này đi sâu vào luồng xử lý runtime.

## 1. Ai gọi tới service này?

| Người gọi | Gọi qua đâu | Mục đích gọi | Endpoint dùng |
|---|---|---|---|
| **Admin (người, qua trình duyệt)** | `http://localhost:8081` (trực tiếp, từ máy host) | Quản trị Realm/Client/User qua Admin Console | `/admin/master/console/...`, Admin REST API |
| **Client/tester (người hoặc script, qua `curl`)** | `http://localhost:8081` (từ máy host) **hoặc** gọi từ trong một container khác | Lấy Access Token để test `/secure` | `POST /realms/realm_nhom13/protocol/openid-connect/token` |
| **`application-backend-server` (Flask)** | `http://authentication-identity-server:8080` (hostname nội bộ Docker, qua `cloud-net`) | Tải JWKS để verify chữ ký JWT của token mà client gửi tới `/secure` | `GET /realms/realm_nhom13/protocol/openid-connect/certs` |
| **`api-gateway-proxy-server` (Nginx)** | `http://authentication-identity-server:8080` (hostname nội bộ) | Forward nguyên vẹn request từ client bên ngoài đi vào `/auth/...` | Toàn bộ path phía sau `/auth/` |
| **Trình duyệt người dùng cuối (end user)** | `http://localhost/auth/...` (qua Gateway, cổng 80) | Trong kịch bản Authorization Code flow (login qua trang web) — **hiện dự án chưa triển khai luồng này, chỉ dùng password grant để demo** | `/realms/realm_nhom13/protocol/openid-connect/auth` (chưa dùng thực tế) |

**Điểm quan trọng:** `authentication-identity-server` **không tự chủ động gọi ai** — nó chỉ là bên phục vụ (server), luôn đóng vai trò nhận request. Không có luồng nào trong dự án mà Keycloak gọi ngược lại `application-backend-server` hay service khác.

## 2. Hai "cửa vào" khác nhau của cùng một Keycloak

```
                         ┌───────────────────────────────┐
  (A) Máy host/Admin ───▶│ http://localhost:8081          │
      (curl, browser)    │                                 │
                         │   authentication-identity-server│
  (B) Container khác ───▶│  :8080 (bên trong cloud-net)    │
      (Flask, Nginx)     │ http://authentication-identity- │
                         │        server:8080              │
                         └───────────────────────────────┘
```

Vì `KC_HOSTNAME_STRICT=false` và không set `KC_HOSTNAME` (xem `README.md` mục 6), Keycloak trả về `iss` (issuer) trong JWT khớp với **đúng hostname mà request đến dùng**:

- Gọi qua (A) `localhost:8081` → token có `iss = http://localhost:8081/realms/realm_nhom13`.
- Gọi qua (B) `authentication-identity-server:8080` → token có `iss = http://authentication-identity-server:8080/realms/realm_nhom13`.

Vì Flask verify issuer theo (B), **token phải được lấy bằng cách gọi qua route (B)** để dùng được với `/secure`. Đây là lý do khi test thực tế, lệnh lấy token phải chạy **từ trong container** (`docker exec application-backend-server curl ...` hoặc tương đương), không lấy từ `localhost:8081` trên máy host nếu mục đích là test `/secure`.

## 3. Luồng 1 — Admin quản trị Realm/Client/User (qua Admin Console hoặc Admin REST API)

**Ai gọi:** người quản trị (hoặc script dùng Admin REST API thay cho click UI).

```
Admin ──POST──▶ /realms/master/protocol/openid-connect/token
                body: client_id=admin-cli, grant_type=password,
                      username=admin, password=admin
   │
   ▼
Keycloak xử lý trong REALM "master" (realm quản trị riêng, tách biệt
với "realm_nhom13"):
   1. Tìm client "admin-cli" trong realm master (client có sẵn, built-in)
   2. Xác thực username/password của user "admin" (user bootstrap từ
      KC_BOOTSTRAP_ADMIN_USERNAME/PASSWORD)
   3. Ký Access Token cho phép gọi Admin REST API
   │
   ▼
200 OK, trả admin access_token
   │
   ▼
Admin ──GET/POST/PUT──▶ /admin/realms/realm_nhom13/...
                Header: Authorization: Bearer <admin_access_token>
   │
   ▼
Keycloak kiểm tra token có quyền quản trị (role admin) không
   │
   ├─ Không đủ quyền → 403
   │
   ▼ (đủ quyền)
Thực hiện thao tác CRUD trên Realm/Client/User/Credential
   (ví dụ: PUT .../users/{id}/reset-password để set mật khẩu — xem
    README.md mục 8.1, vì import tự động không giữ được mật khẩu)
   │
   ▼
200/204, thay đổi được ghi vào dữ liệu Keycloak (persist qua volume
keycloak_data)
```

**Thực tế đã dùng luồng này cho:** set lại mật khẩu user `sv01` sau khi `--import-realm` không áp dụng được credential, và thêm `email`/`emailVerified` cho user để tránh bị required action chặn.

## 4. Luồng 2 — Client lấy Access Token (Resource Owner Password Credentials Grant)

**Ai gọi:** bất kỳ client nào cần token để gọi `/secure` — trong dự án hiện tại là lệnh `curl` thủ công khi test, không phải một service tự động nào gọi định kỳ.

```
Client ──POST──▶ {issuer}/protocol/openid-connect/token
                 Content-Type: application/x-www-form-urlencoded
                 body: client_id=flask-app
                       grant_type=password
                       username=sv01
                       password=Sv01Demo@123!
   │
   ▼
Bên trong Keycloak (realm "realm_nhom13"):
   1. Tìm Client "flask-app" → kiểm tra enabled=true,
      directAccessGrantsEnabled=true (bắt buộc để chấp nhận grant_type=password)
   2. Vì Client là publicClient=true → không yêu cầu client_secret
   3. Tìm User "sv01" trong realm → kiểm tra:
        - enabled=true
        - không có required action nào đang treo (VERIFY_EMAIL, UPDATE_PASSWORD...)
        - mật khẩu khớp với credential đã lưu (hash Argon2)
   4. Nếu mọi điều kiện đạt → build JWT:
        - Header: {"alg": "RS256", "kid": "<key hiện tại của realm>"}
        - Payload: ghép các claim chuẩn (sub, iat, exp, iss, azp...)
          + áp dụng toàn bộ Protocol Mapper đã gắn vào Client, bao gồm
            mapper "flask-app-audience" → thêm "flask-app" vào claim "aud"
        - Ký bằng private key RSA hiện tại của Realm (key pair do Keycloak
          tự sinh, Keycloak giữ private key, chỉ public key được public hoá
          qua JWKS)
   5. Build thêm refresh_token tương ứng
   │
   ├─ Sai mật khẩu/user không tồn tại/client không hỗ trợ grant này
   │     → 400 {"error": "invalid_grant", "error_description": "..."}
   │
   ▼ (đúng)
200 OK:
{
  "access_token": "<JWT>",
  "expires_in": 1800,
  "refresh_token": "<JWT>",
  "refresh_expires_in": 1800,
  "token_type": "Bearer",
  "scope": "email profile"
}
```

**Điểm xử lý nội bộ đáng chú ý:** việc gắn `aud=flask-app` vào token **không phải hành vi mặc định** của Keycloak — nó chỉ xảy ra vì Client `flask-app` có khai báo `protocolMappers` với `oidc-audience-mapper` (xem `realm-export.json`). Nếu xoá mapper này, token vẫn phát hành thành công nhưng `aud` sẽ không chứa `flask-app`, khiến Flask từ chối token ở bước kiểm `audience`.

## 5. Luồng 3 — `application-backend-server` tải JWKS để verify token

**Ai gọi:** chính `authentication-identity-server` không chủ động, mà `application-backend-server` **chủ động gọi vào** mỗi khi cần verify một `kid` không có trong cache (hoặc cache đã hết TTL 600s). Đây là luồng gọi service-to-service duy nhất đi **vào** `authentication-identity-server` từ một service khác trong hệ thống.

```
application-backend-server (khi xử lý GET /secure)
   │
   ▼
Cần verify chữ ký JWT → tra "kid" trong cache nội bộ (SigningKeys)
   │
   ├─ Có trong cache & còn hạn → dùng luôn, KHÔNG gọi Keycloak
   │
   ▼ (cache miss hoặc hết hạn)
GET http://authentication-identity-server:8080/realms/realm_nhom13/
        protocol/openid-connect/certs
   │
   ▼
Bên trong Keycloak:
   1. Route nhận request GET .../certs — đây là endpoint PUBLIC,
      không cần Authorization header
   2. Lấy toàn bộ key pair hiện tại (và các key cũ chưa hết hạn, nếu
      Keycloak đã rotate) được cấu hình cho realm "realm_nhom13"
   3. Với mỗi key, chỉ export phần PUBLIC (n, e theo chuẩn RSA JWK),
      KHÔNG BAO GIỜ export private key
   4. Trả về JSON chuẩn JWKS:
      {
        "keys": [
          {"kid": "...", "kty": "RSA", "alg": "RS256", "use": "sig",
           "n": "...", "e": "AQAB", ...}
        ]
      }
   │
   ▼
200 OK, application-backend-server nhận JWKS, lưu cache 600s, tìm key
có "kid" khớp header JWT, dùng public key đó để verify chữ ký (RS256)
```

**Trường hợp lỗi:**

```
Keycloak không phản hồi được (container tắt, network lỗi, timeout 5s)
   │
   ▼
application-backend-server: requests.RequestException
   │
   ▼
raise IdentityUnavailable
   │
   ▼
GET /secure trả 503 {"error": "Identity provider unavailable"}
```

Chi tiết đầy đủ phía Flask đã có ở `application-backend-server/docs/API.md` (endpoint `/secure`) và `application-backend-server app.py` (`class SigningKeys`).

## 6. Luồng 4 — API Gateway forward `/auth/...`

**Ai gọi:** client bên ngoài (trình duyệt/`curl`) gọi vào Gateway ở cổng `80`, Gateway chuyển tiếp nguyên vẹn sang Keycloak.

```
Client ──GET/POST──▶ http://localhost/auth/realms/realm_nhom13/...
   │
   ▼
api-gateway-proxy-server (Nginx), location /auth/ matched
   proxy_pass http://authentication-identity-server:8080/
   (Nginx cắt tiền tố "/auth/" trước khi forward — xem docs/08-api-gateway.md)
   │
   ▼
application-backend... KHÔNG, thẳng tới authentication-identity-server:8080
   nhận đúng request như nếu gọi trực tiếp :8080, xử lý y hệt Luồng 1/2
   tuỳ vào path cụ thể phía sau "/auth/"
   │
   ▼
Response forward ngược lại nguyên vẹn về Client qua Gateway
```

**Rủi ro đã ghi nhận ở `README.md` mục 11:** route này forward toàn bộ, bao gồm cả path Admin Console (`/auth/admin/...`). Nếu Gateway public ra ngoài thật, cần giới hạn chỉ cho phép các path cần thiết (`/auth/realms/...`), tránh để ai cũng truy cập được trang quản trị Keycloak qua Gateway công khai.

## 7. Tổng hợp: ai gọi gì, Keycloak xử lý ở đâu

| # | Người gọi | Endpoint Keycloak | Realm xử lý | Cần Authorization? | Dữ liệu trả về |
|---|---|---|---|---|---|
| 1 | Admin/script | `POST /realms/master/protocol/openid-connect/token` | `master` | Không (dùng username/password) | Admin access token |
| 1b | Admin/script | `GET/PUT /admin/realms/realm_nhom13/...` | `realm_nhom13` (quản trị qua REST API của realm master) | Có (Bearer admin token) | Dữ liệu Realm/User/Client |
| 2 | Client/tester | `POST /realms/realm_nhom13/protocol/openid-connect/token` | `realm_nhom13` | Không (dùng username/password của end-user) | Access + refresh token |
| 3 | `application-backend-server` | `GET /realms/realm_nhom13/protocol/openid-connect/certs` | `realm_nhom13` | Không (endpoint public) | JWKS (public keys) |
| 4 | Client qua Gateway | Bất kỳ path phía trên, qua `/auth/...` | Tuỳ path | Tuỳ path | Forward nguyên vẹn |

## 8. Những gì Keycloak KHÔNG làm trong dự án này

Để tránh hiểu nhầm phạm vi xử lý:

- Keycloak **không** tự gọi ngược vào `application-backend-server` hay bất kỳ service nào khác (không có webhook, không có event listener cấu hình).
- Keycloak **không** tham gia vào luồng Authorization Code (login qua trang web có redirect) trong thực tế vận hành hiện tại — mặc dù Client `flask-app` có khai báo `standardFlowEnabled: true` và `redirectUris`, dự án chỉ đang dùng password grant (Luồng 2) để demo lấy token bằng `curl`.
- Keycloak **không** lưu trữ hay xử lý trực tiếp dữ liệu nghiệp vụ (sinh viên, object storage...) — vai trò của nó chỉ giới hạn ở việc quản lý danh tính (Identity) và phát hành/chứng thực token.

## 9. Tài liệu liên quan

- `authentication-identity-server/docs/README.md` — thông tin tổng thể service (cấu hình, vấn đề đã gặp, kết quả test).
- `application-backend-server/docs/API.md` — chi tiết endpoint `/secure` phía tiêu thụ token.
- `docs/08-api-gateway.md` — cách route `/auth/` được cấu hình ở Nginx.
