# Kế hoạch triển khai Authentication Server – MyMiniCloud

## 0. Tình trạng hiện tại (cập nhật theo dự án thực tế)

Plan này đã được viết lại để khớp với những gì **đã có trong `docker-compose.yml` và code backend**, không còn dùng thông số nháp ban đầu (`minicloud`/`myapp`). Việc còn lại tập trung vào các phần **chưa làm**, xếp theo thứ tự ưu tiên để hệ thống chạy được end-to-end.

| Hạng mục | Trạng thái |
|---|---|
| Service `authentication-identity-server` trong `docker-compose.yml` | ✅ Đã có (image, port, network, biến môi trường admin) |
| Realm name thống nhất `realm_nhom13` | ✅ Đã thống nhất trong compose + `app.py` (`OIDC_ISSUER`) |
| Client ID thống nhất `flask-app` | ✅ Đã thống nhất trong compose + `app.py` (`OIDC_AUDIENCE`) |
| Flask backend xác minh JWT (`/secure`) | ✅ Đã viết xong: JWKS cache 600s, refresh khi gặp `kid` lạ, kiểm `iss/aud/exp`, phân biệt 503 (identity unavailable) / 401 (token sai) |
| API gateway route `/auth/` → Keycloak | ✅ Đã có trong `nginx.conf` |
| **Volume lưu dữ liệu Keycloak** | ✅ Đã thêm `keycloak_data:/opt/keycloak/data` vào compose |
| **Pin version image Keycloak** | ✅ Đổi từ `:latest` sang `quay.io/keycloak/keycloak:26.4.0` |
| **Realm `realm_nhom13` + Client `flask-app` + User `sv01` thực tế trên Keycloak** | ✅ Đã provision qua `realm-export.json` tự import, user `sv01` có mật khẩu hợp lệ (đặt qua Admin API sau khi phát hiện realm import không giữ credential) |
| **Import tự động realm khi container khởi động** (`--import-realm`) | ✅ Đã cấu hình `command: ["start-dev", "--import-realm"]` + mount `realm-export.json` vào `/opt/keycloak/data/import/` |
| Kiểm thử lấy Access Token | ✅ Lấy token thành công qua `curl` (public client, không cần secret); decode JWT xác nhận `iss=http://authentication-identity-server:8080/realms/realm_nhom13`, `aud` chứa `flask-app` |
| Kiểm thử `/secure` 401/200 | ✅ Không token → 401; token hợp lệ → 200 kèm `preferred_username`; đã test cả gọi trực tiếp backend và qua Gateway `/api/secure` |
| Minh chứng, báo cáo, triển khai EC2 | ❌ Chưa làm |

**Kết luận:** Toàn bộ chuỗi Realm → Client → User → Token → `/secure` đã chạy được thật (local), kể cả qua API Gateway. Phần còn lại là bảo mật trước khi coi là "xong" (đổi mật khẩu admin mặc định) và triển khai/minh chứng trên AWS EC2.

**Lưu ý phát sinh trong quá trình thực thi (chưa có trong plan gốc):**
- Realm import (`--import-realm`) **không giữ được mật khẩu** đặt trong `credentials` của file export gốc dù định dạng đúng cú pháp — Keycloak báo `invalid_grant: Account is not fully set up` khi lấy token. Phải đặt lại mật khẩu qua Admin REST API (`PUT /admin/realms/{realm}/users/{id}/reset-password`) sau khi realm được import.
- User cần có `email` hợp lệ để không bị chặn bởi required action `VERIFY_EMAIL`/`UPDATE_PROFILE` ngầm định của realm mặc định — đã thêm `email: sv01@minicloud.local`, `emailVerified: true`.
- Do những phát sinh trên, quy trình B3/B4 nên được xem là **bán tự động**: import Realm/Client tự động hoạt động tốt, nhưng mật khẩu User cần một bước set lại qua Admin API sau khi container khởi động lần đầu (xem script trong mục B3 cập nhật dưới đây).

## 1. Thông số chính thức (đã dùng trong dự án, không đổi)

| Hạng mục | Giá trị thực tế |
|---|---|
| Service / container | `authentication-identity-server` |
| Docker Network | `cloud-net` |
| Cổng nội bộ | `8080` |
| Cổng máy local | `8081` |
| Realm | `realm_nhom13` |
| OIDC Client ID | `flask-app` |
| Audience kỳ vọng trong JWT | `flask-app` |
| Issuer kỳ vọng (Flask kiểm tra) | `http://authentication-identity-server:8080/realms/realm_nhom13` |
| JWKS URL (Flask dùng) | `{issuer}/protocol/openid-connect/certs` |
| User thử nghiệm | `sv01` |
| Thuật toán xác minh JWT | `RS256` |
| Backend API | `/hello` (công khai), `/student`, `/students-db` (công khai), `/secure` (yêu cầu token) |
| Admin bootstrap | `admin` / `admin` (chỉ demo local) |

**Quan trọng:** Vì Flask chạy trong container dùng hostname nội bộ `authentication-identity-server:8080` để lấy cả issuer và JWKS, nên **không dùng `KC_HOSTNAME=http://localhost:8081`** như bản nháp cũ — làm vậy sẽ khiến issuer trong JWT là `localhost` còn Flask xác minh issuer là hostname nội bộ, token sẽ luôn bị từ chối. Phải giữ nguyên cách tiếp cận hiện tại: không set `KC_HOSTNAME`, dùng `KC_HOSTNAME_STRICT=false`, và khi tạo Realm/Client/test token đều thực hiện qua `http://localhost:8081` (cùng Keycloak instance, Keycloak tự nhận diện hostname theo request).

## 2. Giai đoạn A – Việc đã hoàn thành (không cần làm lại)

- [x] Service Keycloak trong `docker-compose.yml`: image, port `8081:8080`, network `cloud-net`, biến môi trường admin.
- [x] Thống nhất Realm `realm_nhom13` và Client `flask-app` giữa compose và `application-backend-server/app.py`.
- [x] Flask `/hello` công khai, `/secure` yêu cầu Bearer token.
- [x] Logic xác minh JWT trong Flask: JWKS cache, refresh theo `kid`, kiểm `iss/aud/exp`, lỗi 503 khi identity provider không truy cập được, 401 khi token không hợp lệ.
- [x] API Gateway route `/auth/` trỏ sang Keycloak.

## 3. Giai đoạn B – Việc ưu tiên cao: làm Keycloak bền vững và tự provision

### B1. Thêm volume lưu dữ liệu Keycloak

Sửa `docker-compose.yml`, thêm vào service `authentication-identity-server`:

```yaml
    volumes:
      - keycloak_data:/opt/keycloak/data
```

Và thêm vào mục `volumes:` ở đầu file:

```yaml
  keycloak_data:
```

- [ ] Container recreate không làm mất Realm/Client/User.

### B2. Pin version image Keycloak

Thay `quay.io/keycloak/keycloak:latest` bằng một bản cụ thể, ví dụ `quay.io/keycloak/keycloak:26.4.0`, để tránh thay đổi hành vi bất ngờ khi pull lại image.

- [ ] Image Keycloak được pin version cụ thể.

### B3. Tạo Realm, Client, User — đã làm bằng `realm-export.json` tự import (không cần làm tay qua Admin Console)

Thay vì tạo tay qua giao diện, đã viết sẵn `authentication-identity-server/realm-export.json` chứa Realm `realm_nhom13`, Client `flask-app` (public client, `directAccessGrantsEnabled`, audience mapper `flask-app`), và User `sv01`. File này được mount vào `/opt/keycloak/data/import/` và Keycloak tự import nhờ `--import-realm`.

**Phát sinh đã xử lý:** Realm import giữ đúng Client/mapper nhưng **không giữ mật khẩu User** từ trường `credentials` trong file export (Keycloak báo `invalid_grant: Account is not fully set up`). Phải set lại mật khẩu bằng Admin REST API ngay sau khi container khởi động lần đầu:

```bash
ADMIN_TOKEN=$(curl -s -X POST http://localhost:8081/realms/master/protocol/openid-connect/token \
  -d "client_id=admin-cli" -d "grant_type=password" -d "username=admin" -d "password=admin" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
USER_ID=$(curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  "http://localhost:8081/admin/realms/realm_nhom13/users?username=sv01" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")
curl -s -X PUT -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  "http://localhost:8081/admin/realms/realm_nhom13/users/$USER_ID/reset-password" \
  -d '{"type":"password","value":"Sv01Demo@123!","temporary":false}'
```

Cũng cần đảm bảo user có `email` hợp lệ (đã thêm `sv01@minicloud.local` vào export) để không bị required action chặn.

- [x] Realm `realm_nhom13` tồn tại (tự import).
- [x] Client `flask-app` tồn tại, audience mapper gắn `aud=flask-app` đúng (xác nhận qua decode JWT).
- [x] User `sv01` xác thực được bằng mật khẩu `Sv01Demo@123!` sau bước reset-password.

### B4. Export Realm để tái dựng tự động — đã cấu hình

`docker-compose.yml` đã cập nhật:

```yaml
    command: ["start-dev", "--import-realm"]
    volumes:
      - keycloak_data:/opt/keycloak/data
      - ./authentication-identity-server/realm-export.json:/opt/keycloak/data/import/realm-export.json:ro
```

- [x] File `realm-export.json` không còn trống, chứa Realm `realm_nhom13`, Client `flask-app`, User `sv01`.
- [x] Đã kiểm thử: xoá volume (`docker compose rm -f` + `docker volume rm nhom13minicloud_keycloak_data`) rồi `docker compose up -d` — Realm/Client tự tạo lại đúng qua `--import-realm` (log xác nhận `Realm 'realm_nhom13' imported`). Chỉ còn bước set lại mật khẩu `sv01` qua Admin API (xem B3) cần chạy lại sau mỗi lần dựng từ đầu — nên cân nhắc viết thành script `seed-users.sh` cho nhóm dùng lại.

> Lưu ý bảo mật: `realm-export.json` hiện chứa mật khẩu demo `Sv01Demo@123!` ở dạng plaintext trong trường `credentials` (dù Keycloak không áp dụng nó khi import, trường này vẫn tồn tại trong file). Nếu repo công khai, nên thay bằng việc set qua script Admin API riêng, không để mật khẩu plaintext trong file commit Git.

## 4. Giai đoạn C – Kiểm thử lấy Access Token

```bash
curl -X POST \
  http://localhost:8081/realms/realm_nhom13/protocol/openid-connect/token \
  -d "client_id=flask-app" \
  -d "client_secret=YOUR_CLIENT_SECRET" \
  -d "grant_type=password" \
  -d "username=sv01" \
  -d "password=Sv01Demo@123!"
```

Nếu Client là public (không bật Client authentication), bỏ `client_secret`.

- [x] Nhận HTTP 200 với `access_token`, `token_type`, `expires_in`.
- [x] Decode JWT: `iss = http://authentication-identity-server:8080/realms/realm_nhom13`, `aud` chứa `flask-app` (xác nhận qua gọi `curl` trong `application-backend-server`).
- [ ] Trường hợp lỗi: sai mật khẩu / sai client secret → yêu cầu token thất bại, chưa test riêng (vẫn nên làm trước khi báo cáo, nhưng Keycloak trả `invalid_grant` theo đúng chuẩn OIDC nên rủi ro thấp).

> Client `flask-app` là **public client** (không cần `client_secret`) nên lệnh `curl` thực tế bỏ tham số đó, khác với ví dụ confidential client trong bản nháp gốc.

## 5. Giai đoạn D – Kiểm thử tích hợp Flask `/secure`

- [x] `GET /secure` không có token → 401 (xác nhận qua gọi trực tiếp và qua Gateway).
- [x] `GET /secure` có token sai (`garbage.token.here`) → 401.
- [x] `GET /secure` có token hợp lệ → 200 kèm `preferred_username: "sv01"` (cả gọi trực tiếp `localhost:8085/secure` và qua Gateway `http://localhost/api/secure`).
- [ ] `GET /secure` có token hết hạn → 401 (chưa test riêng trường hợp `exp` quá khứ; access token mặc định sống 1800s nên khó test nhanh, có thể bỏ qua hoặc tạo token với `accessTokenLifespan` ngắn để demo).
- [x] Tắt tạm Keycloak, gọi `/secure` với token cũ → vẫn trả **200** (không phải 503) vì JWKS đã được cache 600s trong Flask trước khi tắt Keycloak — đúng hành vi thiết kế cache, không phải lỗi. Để demo đúng case 503, cần tắt Keycloak **trước** khi Flask từng load JWKS lần nào (ví dụ restart cả 2 service theo thứ tự: tắt Keycloak → restart Flask → gọi `/secure`).
- [x] Kiểm thử cả gọi trực tiếp `application-backend-server:8085/secure` và qua Gateway `http://localhost/api/secure`.

## 6. Giai đoạn E – Bảo mật trước khi coi là "xong"

- [ ] Đổi `KC_BOOTSTRAP_ADMIN_PASSWORD` sang giá trị khác `admin`, đưa vào biến môi trường `.env` không commit Git.
- [ ] Xác nhận `start-dev` chỉ dùng cho demo/lab; ghi rõ trong báo cáo đây không phải cấu hình production (thiếu HTTPS, thiếu DB bền vững riêng cho Keycloak).
- [ ] Không commit Client Secret thật vào Git; nếu cần chia sẻ trong nhóm, dùng kênh riêng hoặc `.env`.

## 7. Giai đoạn F – Triển khai AWS EC2

- [ ] Xác nhận `docker compose up -d` chạy đúng toàn bộ 10 service trên EC2 (dùng đúng `docker-compose.yml` hiện tại, không có service Keycloak trùng tên).
- [ ] Không trùng cổng host `8081` với service khác trên EC2.
- [ ] Thay các hostname giả định `localhost` trong tài liệu/test script bằng IP hoặc domain EC2 thực tế; ưu tiên HTTPS nếu có domain.
- [ ] Kiểm tra lại toàn bộ luồng login → lấy token → gọi `/secure` ngay trên EC2.
- [ ] Do đã có `--import-realm` (giai đoạn B4), Realm/Client sẽ tự khởi tạo lại trên EC2 mà không cần làm tay lại Admin Console.

## 8. Giai đoạn G – Minh chứng và báo cáo

- [ ] `docker compose ps` cho thấy `authentication-identity-server` đang Running, kèm volume `keycloak_data` tồn tại.
- [ ] Ảnh chụp Admin Console đăng nhập thành công.
- [ ] Ảnh chụp Realm `realm_nhom13`, Client `flask-app` (ẩn Client Secret), User `sv01`.
- [ ] Log/ảnh phản hồi cấp Access Token (ẩn token và secret).
- [ ] Log/ảnh `/secure` trả 401 khi thiếu token và 200 khi có token hợp lệ.
- [ ] Ảnh/log kết quả chạy trên EC2.

**Nội dung báo cáo phần Authentication Server:**
1. Vai trò Authentication Server trong MyMiniCloud.
2. Lý do dùng Keycloak; khái niệm Realm, Client, User, JWT, OIDC.
3. Kiến trúc kết nối Keycloak – Flask – API Gateway, giải thích vì sao issuer/JWKS dùng hostname nội bộ `authentication-identity-server:8080` thay vì `localhost`.
4. Cấu hình Docker Compose, biến môi trường, volume, `--import-realm`.
5. Quy trình xác thực và kết quả kiểm thử thành công/thất bại.
6. Khó khăn, giới hạn `start-dev`, hướng cải tiến bảo mật (đổi mật khẩu mặc định, HTTPS, DB riêng cho Keycloak).

## 9. Tiêu chí nghiệm thu

| Mức | Tiêu chí |
|---|---|
| Đã đạt | Hạ tầng Compose, thống nhất Realm/Client/Issuer, code Flask xác minh JWT hoàn chỉnh |
| Đã đạt | Volume bền vững + Realm/Client/User được provision và export tự import (`--import-realm`), đã kiểm thử tái dựng từ đầu |
| Đã đạt | Lấy Access Token thành công qua `curl`; `/secure` trả đúng 401 (thiếu/sai token) và 200 (token hợp lệ), qua cả backend trực tiếp và Gateway `/api/secure` |
| Chưa đạt | Test riêng case 503 (identity provider unavailable) và case token hết hạn; test trường hợp sai mật khẩu/sai client lúc lấy token |
| Chưa đạt | Siết bảo mật (đổi mật khẩu admin mặc định, `.env`) |
| Yêu cầu toàn dự án, chưa đạt | Chạy đúng trên AWS EC2 với cấu hình đã export |
| Bàn giao, chưa đạt | Minh chứng (ảnh chụp/log), báo cáo, thông số kết nối cho nhóm |

## 10. Thứ tự thực hiện đề xuất (đã cập nhật theo tiến độ thực tế)

1. ~~**Buổi 1:** Thêm volume `keycloak_data`, pin version image, tạo Realm `realm_nhom13` / Client `flask-app` / User `sv01`, export `realm-export.json`, cấu hình `--import-realm`.~~ **Đã hoàn thành.**
2. ~~**Buổi 2:** Lấy Access Token qua `curl`, kiểm tra `iss/aud`.~~ **Đã hoàn thành** (còn thiếu test case lỗi sai mật khẩu, xem mục 4).
3. ~~**Buổi 3:** Kiểm thử `/secure` 401/200, qua cả backend trực tiếp và Gateway.~~ **Đã hoàn thành** (còn thiếu test case 503 đúng điều kiện và case token hết hạn, xem mục 5).
4. **Buổi 4 (còn lại):** Test bổ sung case lỗi/503/hết hạn → Siết bảo mật (đổi mật khẩu admin, `.env`, không commit mật khẩu plaintext trong `realm-export.json`) → viết script `seed-users.sh` để set lại mật khẩu `sv01` sau mỗi lần dựng từ đầu → triển khai EC2 → chụp minh chứng → hoàn thiện báo cáo.

> Thời lượng trên chỉ là lịch đề xuất, không phải thời hạn do giảng viên quy định.

---

**Nguồn:** `final_cc.pdf` do người dùng cung cấp (yêu cầu 9 server, cấu hình Keycloak, demo Authentication) kết hợp với rà soát thực tế `docker-compose.yml` và `application-backend-server/app.py` tại thời điểm cập nhật plan này. Thông số Realm (`realm_nhom13`) và Client (`flask-app`) được giữ theo đúng những gì nhóm đã thống nhất và đưa vào code, thay cho bản nháp ban đầu (`minicloud`/`myapp`).
