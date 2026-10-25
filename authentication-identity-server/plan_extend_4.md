# PLAN — MỞ RỘNG 4: AUTHENTICATION IDENTITY SERVER (0,5 điểm)

**Dự án:** MyMiniCloud — Nhóm 13
**Service:** `authentication-identity-server` (Keycloak 26.4.0), liên kết `application-backend-server` (Flask), mạng `cloud-net`
**Trạng thái:** Đã thực thi và nghiệm thu bằng lệnh (xem mục 6). Còn lại: chụp minh chứng (mục 7).

> Realm của Mở rộng 4 là **`realm_52300076`** (realm mới, riêng cho bài nộp), chứa `sv01`, `sv02` và client `flask-app`. Realm `realm_nhom13` của hệ thống được giữ nguyên, chỉ còn `sv01`. Realm, client, mapper và user được provision bằng file import, không tạo tay trên giao diện.

## 0. Yêu cầu và Definition of Done

Tạo Realm mới `realm_52300076`, hai user `sv01` và `sv02` (mật khẩu không tạm thời), public client `flask-app` bật Direct Access Grants. Trỏ `OIDC_ISSUER` và `OIDC_REALM` của Flask sang realm mới. Lấy Access Token từ Token Endpoint và gọi `/secure` nhận HTTP 200.

- [x] Keycloak chạy trong `cloud-net`, Admin Console mở được tại `http://localhost:8081/admin/master/console/`.
- [x] Realm `realm_52300076` tồn tại (không dùng `master`), tách biệt với `realm_nhom13`.
- [x] `sv01`, `sv02` thuộc `realm_52300076`, Enabled, mật khẩu Temporary = OFF, không có Required Action.
- [x] Client `flask-app` trong `realm_52300076`: public (Client authentication OFF), Direct Access Grants ON, có Audience Mapper.
- [x] Access Token của cả hai user có `iss` thuộc `realm_52300076`, `aud` chứa `flask-app`.
- [x] `/secure` không token hoặc token sai trả 401; token `sv01` và `sv02` của realm mới trả 200 đúng `preferred_username`.
- [x] Token của `realm_nhom13` bị `/secure` từ chối (401) khi backend đang trỏ sang realm mới.

## 1. So sánh plan gốc với dự án và quyết định

| Nội dung plan gốc | Hiện trạng dự án | Quyết định |
|---|---|---|
| Tạo Realm, Client, User bằng giao diện | Dự án provision bằng file import (`--import-realm`) | Dùng file import; giao diện chỉ để kiểm tra |
| Realm tên `realm_nhom13` | `realm_nhom13` là realm của cả hệ thống, backend đang dùng | Giữ nguyên `realm_nhom13`; tạo realm riêng `realm_52300076` cho Mở rộng 4 (file `realm_52300076.json`) |
| Backend cố định một realm | `app.py` lấy JWKS và kiểm `iss` theo `OIDC_ISSUER`, `OIDC_REALM`, `OIDC_ISSUER_ALIASES` | Không sửa `app.py`. Dùng Compose override để đổi sang realm mới khi demo (mục 5) |
| Audience Mapper tạo tay | Mapper đã khai báo trong file import | Có sẵn mapper `flask-app-audience` trong `realm_52300076.json` |
| Bỏ `KC_HOSTNAME` | Đã gỡ ở nhánh `fix-keycloak-admin-console-hostname` | Giữ `KC_HOSTNAME_STRICT=false`, không đặt `KC_HOSTNAME` |
| `iss` phải khớp tuyệt đối | `app.py` chấp nhận nhiều host của cùng realm | Lấy token qua `localhost:8081` hoặc gateway đều dùng được; host lạ vẫn bị 401 |
| Sao lưu trước khi recreate | Đã có volume `keycloak_data` | Chỉ cần kiểm tra mount |
| Thông báo 401 là `Missing Bearer token` | Thực tế là `Missing or invalid Bearer token` | Sửa kỳ vọng theo thực tế |

## 2. Thông số chuẩn

| Hạng mục | Giá trị |
|---|---|
| Container Keycloak / Flask | `authentication-identity-server` / `application-backend-server` |
| URL từ máy host | Keycloak `http://localhost:8081`, Flask `http://localhost:8085`, Gateway `http://localhost` |
| URL nội bộ | `http://authentication-identity-server:8080` |
| Realm Mở rộng 4 / Client | `realm_52300076` / `flask-app` (public, Direct Access Grants ON) |
| Users | `sv01`, `sv02`; mật khẩu lab khai báo trong `realm_52300076.json` |
| `OIDC_ISSUER` khi demo | `http://authentication-identity-server:8080/realms/realm_52300076` |
| `OIDC_REALM` khi demo | `realm_52300076` |
| `OIDC_AUDIENCE` | `flask-app` |
| Realm mặc định của hệ thống | `realm_nhom13` (chỉ có `sv01`) |
| Admin Keycloak | `admin` / `admin` (chỉ demo local) |

## 3. Giai đoạn A — Kiểm tra hiện trạng (đã thực hiện)

```bash
docker compose ps authentication-identity-server application-backend-server
docker inspect authentication-identity-server --format '{{json .Mounts}}'   # phải có volume keycloak_data
docker exec application-backend-server env | grep ^OIDC_
```

Không chạy `docker compose down -v` hay `docker volume prune`.

## 4. Giai đoạn B — Tạo `realm_52300076` (đã thực hiện)

**4.1. File định nghĩa.** `authentication-identity-server/realm_52300076.json` khai báo realm, client `flask-app` (public, Direct Access Grants, Audience Mapper) và hai user `sv01`, `sv02` có `email`, `emailVerified: true`, `requiredActions: []`, mật khẩu `temporary: false`. `Dockerfile` copy file này vào thư mục import cùng `realm-export.json`.

**4.2. Áp dụng lên Keycloak đang chạy.** `--import-realm` dùng chiến lược `IGNORE_EXISTING` và volume `keycloak_data` đã có dữ liệu, nên realm mới không tự import vào Keycloak đang chạy. Tạo bằng Admin API (idempotent, chỉ tạo khi chưa có):

```bash
KC=http://localhost:8081
A=$(curl -s -X POST $KC/realms/master/protocol/openid-connect/token \
  -d client_id=admin-cli -d grant_type=password -d username=admin -d password=admin \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
curl -s -o /dev/null -w "HTTP %{http_code}\n" -X POST -H "Authorization: Bearer $A" \
  -H "Content-Type: application/json" $KC/admin/realms \
  -d @authentication-identity-server/realm_52300076.json     # 201 nếu tạo mới, 409 nếu đã tồn tại
```

Kết quả: HTTP 201; realm có `sv01`, `sv02` đều Enabled, `requiredActions=[]`.

**4.3. Gỡ `sv02` khỏi `realm_nhom13`.** Trước đó `sv02` được thêm nhầm vào `realm_nhom13` (cả trong `realm-export.json` lẫn Keycloak đang chạy). Đã gỡ khỏi `realm-export.json` và xóa khỏi Keycloak đang chạy (HTTP 204). `realm_nhom13` chỉ còn `sv01`; `sv01` ở `realm_nhom13` giữ nguyên, kể cả `email` đã thêm.

**4.4. Kiểm tra import từ đầu.** Build image từ `authentication-identity-server/Dockerfile` và chạy không có volume. Log Keycloak báo import cả hai realm. Kết quả lấy token:

| Realm | User | Kết quả |
|---|---|---|
| `realm_52300076` | `sv01`, `sv02` | HTTP 200, có `access_token` |
| `realm_nhom13` | `sv01` | HTTP 200 |
| `realm_nhom13` | `sv02` | HTTP 401 `invalid_grant` (đúng, user đã gỡ) |

Cả hai realm lấy token được ngay sau import, không cần đặt lại mật khẩu bằng Admin API. Điều này khác ghi chú "import không giữ mật khẩu" trong `plan.md`. Chưa thử lại file cũ không có `email`, nên chưa biết `email` có phải nguyên nhân hay không.

## 5. Giai đoạn C — Trỏ backend sang realm mới và gọi `/secure`

**5.1. Bật realm mới cho backend.** Backend mặc định dùng `realm_nhom13` theo `docker-compose.yml`. Để demo Mở rộng 4, dùng file override `authentication-identity-server/compose.realm_52300076.yml` (đặt `OIDC_ISSUER`, `OIDC_REALM`, `OIDC_AUDIENCE`, `OIDC_ISSUER_ALIASES`):

```bash
docker compose -f docker-compose.yml -f authentication-identity-server/compose.realm_52300076.yml \
  up -d --no-deps application-backend-server
docker exec application-backend-server env | grep -E '^OIDC_(ISSUER|REALM|AUDIENCE)='
```

Kỳ vọng: `OIDC_ISSUER=http://authentication-identity-server:8080/realms/realm_52300076`, `OIDC_REALM=realm_52300076`, `OIDC_AUDIENCE=flask-app`.

**5.2. Lấy token và gọi `/secure`.**

```bash
read -r -s -p 'Password sv01: ' P; echo
TOKEN=$(docker exec -e U=sv01 -e P="$P" application-backend-server python -c '
import os,json,urllib.request,urllib.parse
d=urllib.parse.urlencode({"client_id":"flask-app","grant_type":"password","username":os.environ["U"],"password":os.environ["P"]}).encode()
print(json.load(urllib.request.urlopen("http://authentication-identity-server:8080/realms/realm_52300076/protocol/openid-connect/token",d,timeout=10))["access_token"])')
unset P
curl -i http://localhost:8085/secure -H "Authorization: Bearer $TOKEN"     # kỳ vọng 200
curl -i http://localhost/api/secure   -H "Authorization: Bearer $TOKEN"     # qua gateway, kỳ vọng 200
unset TOKEN
```

Lặp lại với `sv02`. Nếu lấy token từ máy host qua `localhost:8081`, `iss` là `http://localhost:8081/realms/realm_52300076` và vẫn được chấp nhận vì đã khai báo trong `OIDC_ISSUER_ALIASES` của file override.

**5.3. Trả backend về `realm_nhom13` sau khi demo.**

```bash
docker compose up -d --no-deps application-backend-server
docker exec application-backend-server env | grep ^OIDC_ISSUER=
```

Không có file override thì backend quay lại `realm_nhom13`. Đã kiểm tra: `/secure` với token `sv01` của `realm_nhom13` trả 200.

## 6. Bảng nghiệm thu (đã chạy ngày 25/10/2026)

| ID | Kịch bản | Kỳ vọng | Kết quả |
|---|---|---|---|
| AUTH-01 | Admin Console | HTTP 200 | Đạt |
| AUTH-02 | Discovery `realm_52300076` | HTTP 200 | Đạt (Keycloak đang chạy và Keycloak tạm) |
| AUTH-03 | Users `sv01`, `sv02` trong `realm_52300076` (Admin API) | Enabled, `requiredActions=[]` | Đạt |
| AUTH-04 | Client `flask-app` trong `realm_52300076` | Public, Direct Access Grants ON, có mapper | Đạt |
| AUTH-05, 06 | Token `sv01`, `sv02` của realm mới | Có `access_token` | Đạt |
| AUTH-07 | Claim | `iss` = `.../realms/realm_52300076`, `aud` có `flask-app` | Đạt |
| AUTH-08 | `/hello` | HTTP 200 | Đạt |
| AUTH-09 | `/secure` không token | HTTP 401 | Đạt |
| AUTH-10 | `/secure` token sai | HTTP 401 | Đạt |
| AUTH-11 | `/secure` token `sv01` (realm mới) | HTTP 200, `sv01` | Đạt |
| AUTH-12 | `/secure` token `sv02` (realm mới) | HTTP 200, `sv02` | Đạt |
| AUTH-13 | `/api/secure` qua gateway, `sv02` | HTTP 200 | Đạt |
| AUTH-14 | `/secure` với token `realm_nhom13` khi backend trỏ realm mới | HTTP 401 | Đạt |
| AUTH-15 | `sv02` đăng nhập `realm_nhom13` | `invalid_grant` | Đạt |
| AUTH-16 | Import từ đầu (image build từ Dockerfile, không volume) | Cả hai realm lấy token được | Đạt |
| AUTH-17 | Trả backend về `realm_nhom13`, `/secure` token `sv01` | HTTP 200 | Đạt |

## 7. Minh chứng cần chụp (chưa làm)

- [ ] `01-realm-52300076.png`: Realm `realm_52300076` trên Admin Console
- [ ] `02-users.png`: danh sách `sv01`, `sv02` của realm mới
- [ ] `03-flask-app-settings.png`: Client public, Direct Access Grants ON
- [ ] `04-audience-mapper.png`: mapper `flask-app-audience`
- [ ] `05-token-claims.png`: `iss`, `aud`, `azp`, `preferred_username` (không hiện JWT đầy đủ)
- [ ] `06-flask-env.png`: `OIDC_ISSUER`, `OIDC_REALM`, `OIDC_AUDIENCE` (sau khi bật override)
- [ ] `07-secure-200.png`: `/secure` 200 cho `sv01` và `sv02`
- [ ] `08-secure-401.png`: không token và token sai

Không đưa mật khẩu hoặc Access Token thật vào ảnh, Git hay báo cáo. Chụp ảnh `06` và `07` khi backend đang trỏ sang realm mới (mục 5.1), sau đó trả về `realm_nhom13` (mục 5.3).

## 8. Lỗi thường gặp (theo dự án)

| Triệu chứng | Nguyên nhân | Cách xử lý |
|---|---|---|
| Admin Console đăng nhập lỗi | `KC_HOSTNAME` trỏ tên nội bộ, trình duyệt không phân giải được | Không đặt `KC_HOSTNAME` |
| `/secure` 401 với token của realm mới | Backend chưa bật override, vẫn trỏ `realm_nhom13` | Chạy lệnh mục 5.1, kiểm tra `OIDC_ISSUER` trong container |
| `/secure` 401 với token của `realm_nhom13` | Backend đang trỏ realm mới | Đúng thiết kế; trả backend về mặc định (mục 5.3) |
| `/secure` 401 dù token mới | `iss` có host ngoài allowlist | Giải mã `iss`; lấy lại token qua `authentication-identity-server:8080` hoặc mở rộng allowlist |
| `/secure` 401, thiếu `aud` | Thiếu mapper | Mapper `flask-app-audience` có trong `realm_52300076.json`; lấy token mới |
| `invalid_grant` | Sai mật khẩu, user disabled, còn Required Action | Kiểm tra user trên Admin Console |
| Realm mới không có sau khi dựng lại | Volume đã có dữ liệu nên `--import-realm` bỏ qua | Tạo bằng Admin API (mục 4.2), hoặc dựng Keycloak mới với volume trống |
| 503 từ `/secure` | Flask không tải được JWKS | Kiểm tra Keycloak và `cloud-net` |

## 9. Phạm vi và bảo mật

- Direct Access Grants chỉ bật vì đề lab yêu cầu; ứng dụng thật nên dùng Authorization Code Flow với PKCE.
- `start-dev`, HTTP, `admin/admin` và mật khẩu lab trong `realm_52300076.json` chỉ phù hợp local. Trước khi lên EC2 cần đổi mật khẩu, đóng cổng 8081 và giới hạn route `/auth/admin/` ở gateway.
- `azp` không thay thế kiểm tra `aud`; Flask vẫn kiểm `aud`.
- Backend chỉ tin một realm tại một thời điểm (JWKS lấy theo `OIDC_ISSUER`). Cần chạy hai realm song song thì phải sửa `app.py`, chưa làm.
- Không đổi tên `cloud-net`, `authentication-identity-server`, `application-backend-server`.

## 10. Tài liệu đối chiếu

- `final_cc(4).pdf`, mục 4 (Keycloak) và phần Cloud App Integration Practice.
- `authentication-identity-server/plan.md`, `docs/README.md`, `docs/FLOW.md`, `realm-export.json`, `realm_52300076.json`, `compose.realm_52300076.yml`, `application-backend-server/app.py`.
