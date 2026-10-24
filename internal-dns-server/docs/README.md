# Internal DNS Server (BIND9) — Kết quả triển khai

Tài liệu này ghi lại kết quả thực thi `internal-dns-server/plan.md` (đã thực thi, không chỉ là kế hoạch). Phạm vi: local (Docker Desktop), **không bao gồm EC2** theo yêu cầu.

## 1. Trạng thái

- [x] Container `internal-dns-server` chạy ổn định từ Compose chung (`restart: unless-stopped`).
- [x] Tham gia mạng `cloud-net`.
- [x] Đúng image `internetsystemsconsortium/bind9:9.18`.
- [x] Mapping cổng `1053/udp` (host) → `53/udp` (container).
- [x] 4 file cấu hình, mount read-only vào `/etc/bind` (xem mục 3 — có 1 file phát sinh ngoài plan).
- [x] `named-checkconf` và `named-checkzone` chạy thành công.
- [x] `dig` trả đúng 5 bản ghi A.
- [x] Test đổi/giữ SOA serial, restart container, test lại thành công.
- [x] Test truy vấn từ container khác trong `cloud-net` (không chỉ từ host).
- [ ] Triển khai/kiểm thử trên AWS EC2 — **bỏ qua theo yêu cầu**.

## 2. Vấn đề phát sinh ngoài plan: cần thêm file `named.conf`

Plan gốc chỉ yêu cầu 3 file (`named.conf.options`, `named.conf.local`, `db.cloud.local`). Khi chạy thực tế, container khởi động bình thường nhưng `dig` trả `REFUSED` cho mọi truy vấn zone `cloud.local`.

**Nguyên nhân:** image `internetsystemsconsortium/bind9:9.18` đã đóng gói sẵn file `/etc/bind/named.conf` mặc định (cấu hình cho DNS-over-HTTPS/TLS), và file này **không `include`** `named.conf.options`/`named.conf.local`. Việc mount 2 file đó vào `/etc/bind/` không có tác dụng gì nếu file `named.conf` chính không include chúng.

**Cách xử lý:** tạo thêm `internal-dns-server/named.conf`:

```conf
include "/etc/bind/named.conf.options";
include "/etc/bind/named.conf.local";
```

và mount đè lên `/etc/bind/named.conf:ro` trong `docker-compose.yml`. Sau khi thêm, `named-checkconf`/`named-checkzone` chạy OK và `dig` trả đúng kết quả.

## 3. Danh sách file cấu hình thực tế

```text
internal-dns-server/
├── named.conf              # MỚI - include 2 file dưới, bắt buộc để BIND9 load zone
├── named.conf.options       # theo plan
├── named.conf.local         # theo plan
└── db.cloud.local           # theo plan, SOA serial 2026102401
```

`docker-compose.yml` mount cả 4 file (thêm 1 dòng volume cho `named.conf` so với plan gốc).

## 4. Kết quả kiểm thử

### 4.1. Kiểm tra cấu hình

```
$ docker exec internal-dns-server named-checkconf
(exit 0, không lỗi)

$ docker exec internal-dns-server named-checkzone cloud.local /etc/bind/db.cloud.local
zone cloud.local/IN: loaded serial 2026102401
OK
```

### 4.2. `dig` từ host qua `1053/udp`

```
$ dig @127.0.0.1 -p 1053 ns.cloud.local +short
127.0.0.1
$ dig @127.0.0.1 -p 1053 web-frontend-server.cloud.local +short
10.10.10.10
$ dig @127.0.0.1 -p 1053 app-backend.cloud.local +short
10.10.10.20
$ dig @127.0.0.1 -p 1053 minio.cloud.local +short
10.10.10.30
$ dig @127.0.0.1 -p 1053 keycloak.cloud.local +short
10.10.10.40
```

Đúng 100% bảng quy ước A record của nhóm.

### 4.3. SOA record

```
$ dig @127.0.0.1 -p 1053 cloud.local SOA +noall +answer
cloud.local.  3600  IN  SOA  ns.cloud.local. admin.cloud.local. 2026102401 3600 900 604800 3600
```

### 4.4. Restart và kiểm tra lại (persistence)

```
$ docker compose restart internal-dns-server
(container restart thành công)

$ dig @127.0.0.1 -p 1053 app-backend.cloud.local +short
10.10.10.20
$ dig @127.0.0.1 -p 1053 minio.cloud.local +short
10.10.10.30
$ dig @127.0.0.1 -p 1053 keycloak.cloud.local +short
10.10.10.40
```

Dữ liệu zone không mất sau restart vì 4 file cấu hình được bind-mount trực tiếp từ host (không nằm trong container filesystem tạm).

### 4.5. Truy vấn từ container khác trong `cloud-net`

Dùng container tạm `nicolaka/netshoot` (có `dig`), chỉ định rõ DNS server đích là `internal-dns-server` (Docker service name):

```
$ docker run --rm --network cloud-net nicolaka/netshoot \
    dig @internal-dns-server -p 53 web-frontend-server.cloud.local +short
10.10.10.10
```

Xác nhận BIND9 trả lời đúng cho truy vấn phát sinh **trong** Docker network, không chỉ qua cổng host.

## 5. Đối chiếu IP quy ước vs IP thực tế trong `cloud-net`

Đã kiểm tra bằng `docker inspect <container> --format '{{(index .NetworkSettings.Networks "cloud-net").IPAddress}}'`:

| Container | Tên DNS quy ước | IP quy ước (Word) | IP thực tế trong `cloud-net` |
|---|---|---|---|
| `web-frontend-server` | `web-frontend-server.cloud.local` | `10.10.10.10` | `172.19.0.3` |
| `application-backend-server` | `app-backend.cloud.local` | `10.10.10.20` | `172.19.0.11` |
| `object-storage-server` | `minio.cloud.local` | `10.10.10.30` | `172.19.0.8` |
| `authentication-identity-server` | `keycloak.cloud.local` | `10.10.10.40` | `172.19.0.2` |
| `internal-dns-server` | `ns.cloud.local` | `127.0.0.1` | `172.19.0.7` |

**Không khớp** — đúng như cảnh báo ở plan mục 0.1 và 9.1: Docker không tự gán `10.10.10.x` chỉ vì zone file khai báo như vậy. Subnet `cloud-net` hiện tại do Docker tự cấp là `172.19.0.0/16` (xem `docker network inspect cloud-net`), không phải `10.10.10.0/24`.

**Quyết định đã chọn (theo xác nhận của nhóm):** **Phương án A — Demo DNS độc lập.**

- Giữ nguyên 5 A record tĩnh theo Word, dùng để minh chứng mục tiêu DNS (zone, SOA, NS, A record, TTL, caching) hoạt động đúng qua `dig`.
- **Không** dùng các hostname `*.cloud.local` để các service thật sự gọi nhau. Giao tiếp thực tế giữa `application-backend-server`, `object-storage-server`, `authentication-identity-server`... tiếp tục dùng **Docker service name** có sẵn (ví dụ `authentication-identity-server:8080`), như đã cấu hình trong `docker-compose.yml` (biến `OIDC_ISSUER`, `DB_HOST`...).
- Nếu sau này nhóm muốn chuyển sang Phương án B (gán IP tĩnh `10.10.10.x` thật cho 4 container qua `docker-compose.yml`, đổi subnet `cloud-net`), đây là thay đổi ảnh hưởng nhiều service và cần làm riêng, có rà soát kỹ xung đột subnet.

## 6. Checklist còn lại (không thuộc phạm vi đã thực thi)

- [ ] Kiểm thử/triển khai trên AWS EC2 — bỏ qua theo yêu cầu người dùng.
- [ ] Ảnh chụp màn hình đưa vào báo cáo — các lệnh và kết quả ở mục 4 có thể dùng làm log thay thế hoặc tự chụp lại.
