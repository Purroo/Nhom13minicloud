# PLAN - INTERNAL DNS SERVICE (BIND9) | MYMINICLOUD

> **Trạng thái:** Kế hoạch thực thi, chưa xác nhận đã triển khai hoặc kiểm thử thành công.  
> **Phạm vi:** Server số 6 - `internal-dns-server` trong dự án Cloud Computing **MyMiniCloud**.  
> **Nguồn:** (1) `final_cc(3).pdf` - mô tả kiến trúc, cấu hình và bài kiểm thử/mở rộng DNS; (2) `Tài liệu thống nhất tên gọi (1).docx` - quy ước nhóm về tên, image, port, network và 5 bản ghi A.  
> **Nguyên tắc ưu tiên:** Giữ nguyên các giá trị đã chốt ở tài liệu Word; dùng PDF để xác định trình tự triển khai, lệnh kiểm thử và yêu cầu demo. Những đề xuất kỹ thuật bổ sung được ghi rõ là **khuyến nghị**, không tự ý thay đổi quy ước nhóm.

## 0. Mục tiêu và tiêu chí hoàn thành

### 0.1. Mục tiêu

Xây dựng một container **BIND9** chạy trong mạng Docker `cloud-net`, làm authoritative DNS cho zone `cloud.local` và trả đúng các bản ghi A được nhóm thống nhất. Tích hợp cấu hình vào Docker Compose chung của nhóm, kiểm thử qua `dig`, chụp minh chứng và bàn giao tài liệu cấu hình.

**Phân biệt hai mức kiểm thử:**

1. **Bắt buộc theo tài liệu:** BIND9 trả về IP chính xác đã khai báo trong file zone. Ví dụ, truy vấn `web-frontend-server.cloud.local` trả về `10.10.10.10`.
2. **Tích hợp thực tế (kiểm tra thêm):** IP mà DNS trả về phải là địa chỉ đang được gán cho service, nếu muốn ứng dụng kết nối thật sự qua những hostname này. Docker không tự gán IP `10.10.10.x` chỉ vì ta viết các bản ghi A.

### 0.2. Definition of Done (DoD)

- [ ] Container `internal-dns-server` chạy ổn định từ Compose chung.
- [ ] Container tham gia mạng `cloud-net`.
- [ ] Dùng chính xác image `internetsystemsconsortium/bind9:9.18`.
- [ ] Mapping cổng từ host `1053/udp` sang container `53/udp`.
- [ ] Có đủ 3 file cấu hình, được mount read-only vào `/etc/bind`.
- [ ] `named-checkconf` và `named-checkzone` thành công.
- [ ] `dig` trả đúng **5 bản ghi A** trong bảng quy ước.
- [ ] Test thay đổi zone, tăng SOA serial, restart container và test lại thành công.
- [ ] Lưu ảnh/log demo, ghi rõ phần cơ bản và phần mở rộng đã hoàn thành.
- [ ] Bàn giao cấu hình và hướng dẫn thao tác cho nhóm tích hợp/AWS EC2.

## 1. Quy ước bắt buộc của nhóm (KHÔNG tự đổi tên)

| Mục | Giá trị thống nhất | Nguồn |
|---|---|---|
| Thư mục gốc | `Nhom<X>minicloud` (ví dụ `Nhom01minicloud`) | Word - Quy ước 1 |
| Thư mục DNS | `internal-dns-server` | Word - Quy ước 1 |
| Service/container | `internal-dns-server` | Word - Quy ước 1 |
| Docker image | `internetsystemsconsortium/bind9:9.18` | PDF & Word |
| Docker network | `cloud-net` | PDF & Word |
| DNS zone | `cloud.local` | PDF & Word |
| Port nội bộ | `53/udp` | Word - Quy ước 2 |
| Port trên host | `1053/udp` | PDF & Word |
| Docker Compose | `docker-compose.yml` trong thư mục gốc nhóm | PDF |
| Chính sách khởi động lại | `restart: unless-stopped` | PDF - yêu cầu chung |

### 1.1. Bảng bản ghi A đã chốt

| Hostname đầy đủ (FQDN) | Tên ghi trong zone file | IPv4 BẮT BUỘC |
|---|---|---|
| `ns.cloud.local` | `ns` | `127.0.0.1` |
| `web-frontend-server.cloud.local` | `web-frontend-server` | `10.10.10.10` |
| `app-backend.cloud.local` | `app-backend` | `10.10.10.20` |
| `minio.cloud.local` | `minio` | `10.10.10.30` |
| `keycloak.cloud.local` | `keycloak` | `10.10.10.40` |

**Chú ý:** Tài liệu Word yêu cầu `ns.cloud.local = 127.0.0.1`; giữ nguyên để nghiệm thu theo quy ước. Tuy nhiên `127.0.0.1` là loopback của **chính máy đang truy vấn**, không phải IP BIND9 có thể dùng từ container khác. Nếu dùng DNS thực sự để liên lạc xuyên container, nhóm phải thống nhất thêm địa chỉ có thể truy cập của DNS Server; đây là vấn đề tích hợp cần báo cáo, không âm thầm sửa bản ghi chốt.

**Tên DNS khác tên Docker:** `app-backend` không phải `application-backend-server`, `minio` không phải `object-storage-server`, `keycloak` không phải `authentication-identity-server`. Đây là các tên miền A theo quy ước, không phải Docker service aliases tự động.

## 2. Phân chia nhiệm vụ, phụ thuộc, đầu ra

| Giai đoạn | Công việc | Đầu ra kiểm chứng | Phụ thuộc |
|---|---|---|---|
| P0 | Kiểm tra môi trường, network và Compose của nhóm | `docker info`, `docker network inspect cloud-net` | Docker hoạt động |
| P1 | Viết file cấu hình BIND9 | 3 file trong `internal-dns-server/` | Quy ước Word |
| P2 | Ghép service vào Compose chung | Service DNS trong `docker-compose.yml` | Nhóm phụ trách Compose |
| P3 | Kiểm tra cấu hình và khởi chạy | `named-checkconf`, log container | P1-P2 |
| P4 | Test phân giải A records cơ bản | `dig` đúng 5 IPv4 | P3 |
| P5 | Test cập nhật/restart, lưu minh chứng | Ảnh màn hình và log | P4 |
| P6 | Làm việc với nhóm về DNS/IP thực tế | Biên bản quyết định IP/DNS | Nhóm tích hợp |
| P7 | Kiểm thử trên EC2, bàn giao | Kết quả trên EC2; tài liệu demo | Nhóm triển khai EC2 |

## 3. Bước 1 - Chuẩn bị Docker và thư mục

> Chạy các lệnh dưới đây tại **thư mục gốc dự án nhóm**. Thay `Nhom<X>minicloud` bằng tên thật theo nhóm. Trên Windows PowerShell, có thể tạo thư mục bằng `New-Item -ItemType Directory` thay cho `mkdir -p`.

```bash
# Kiểm tra Docker/Compose
docker --version
docker compose version
docker info

# Ví dụ: nếu thư mục gốc chưa được tạo
mkdir -p 'Nhom<X>minicloud/internal-dns-server'
cd 'Nhom<X>minicloud'

# Kiểm tra mạng do nhóm tạo / Compose dùng chung
docker network ls
docker network inspect cloud-net
```

Nếu đang chạy riêng service và mạng chưa tồn tại, dùng `docker network create cloud-net` **chỉ khi đã thống nhất với nhóm**. Nếu Compose chung quản lý mạng, hãy dùng Compose của nhóm thay vì tạo một mạng thứ hai hoặc đổi tên mạng.

Cấu trúc cần đạt:

```text
Nhom<X>minicloud/
├── docker-compose.yml
└── internal-dns-server/
    ├── named.conf.options
    ├── named.conf.local
    └── db.cloud.local
```

**Đầu ra P0:** Docker chạy, biết chính xác thư mục repo/Compose của nhóm, xác nhận `cloud-net` được quản lý thế nào.

## 4. Bước 2 - Viết 3 file cấu hình BIND9

### 4.1. `internal-dns-server/named.conf.options`

**Cấu hình mẫu theo PDF** (dùng cho bài lab nội bộ):

```conf
options {
    directory "/var/cache/bind";
    allow-query { any; };
    recursion yes;
};
```

Giải thích: `directory` là thư mục làm việc; `allow-query` mở quyền truy vấn; `recursion yes` bật đệ quy. Vì đây là DNS nội bộ, **không nên công bố cấu hình đệ quy mở ra Internet**. Trên EC2 nên hạn chế bằng Security Group/binding hoặc siết ACL theo mạng nội bộ, sau khi thống nhất với nhóm.

### 4.2. `internal-dns-server/named.conf.local`

```conf
zone "cloud.local" IN {
    type master;
    file "/etc/bind/db.cloud.local";
};
```

Ý nghĩa: khai báo DNS zone `cloud.local`, dùng file `db.cloud.local` làm dữ liệu authoritative.

### 4.3. `internal-dns-server/db.cloud.local`

**Phiên bản tổng hợp đủ 5 A records theo Word**, giữ cú pháp BIND9 từ PDF:

```dns
$TTL 1H
@   IN SOA ns.cloud.local. admin.cloud.local. (
        2026102401 ; serial - tăng số mỗi lần thay đổi zone
        1H         ; refresh
        15M        ; retry
        1W         ; expire
        1H         ; negative cache TTL
)
@                     IN NS  ns.cloud.local.

ns                    IN A   127.0.0.1
web-frontend-server   IN A   10.10.10.10
app-backend           IN A   10.10.10.20
minio                 IN A   10.10.10.30
keycloak              IN A   10.10.10.40
```

**Lưu ý về SOA:** `2026102401` là số serial **khởi tạo gợi ý** (khác số `1` trong PDF), không phải quy ước bắt buộc của nhóm. Mỗi lần cập nhật zone, tăng serial (ví dụ `2026102402`) để bảo đảm lịch sử thay đổi rõ ràng.

**Đầu ra P1:** 3 file được lưu UTF-8 (không thêm đuôi `.txt`), đúng tên và vị trí.

## 5. Bước 3 - Cấu hình service trong Docker Compose

### 5.1. Thêm **duy nhất** service DNS sau vào `services:` của `docker-compose.yml` chung

```yaml
  internal-dns-server:
    image: internetsystemsconsortium/bind9:9.18
    container_name: internal-dns-server
    ports:
      - "1053:53/udp"
    volumes:
      - ./internal-dns-server/named.conf.options:/etc/bind/named.conf.options:ro
      - ./internal-dns-server/named.conf.local:/etc/bind/named.conf.local:ro
      - ./internal-dns-server/db.cloud.local:/etc/bind/db.cloud.local:ro
    networks:
      - cloud-net
    restart: unless-stopped
```

### 5.2. Chốt cấu hình mạng ở cấp root Compose

Nếu trong Compose chung đã có `cloud-net`, **không khai báo lặp hoặc đổi tên**. Nếu chưa có, nhóm tích hợp thêm:

```yaml
networks:
  cloud-net:
    name: cloud-net
```

Nếu nhóm đã tạo mạng bên ngoài Compose và muốn dùng lại, có thể dùng `external: true` cho `cloud-net` sau khi đã kiểm tra và thống nhất. Hai cách này **không ghép lẫn tùy tiện**.

**Kiểm tra trước khi chạy:**

```bash
docker compose config --services
docker compose config
```

Nếu tên `internal-dns-server` xuất hiện trong danh sách service và Compose không báo lỗi cú pháp, chuyển sang bước tiếp theo.

**Đầu ra P2:** Bản thay đổi Compose DNS đã gửi cho người phụ trách ghép code; không tạo thêm bản Compose riêng có thể xung đột cổng/container name.

## 6. Bước 4 - Khởi động, xem log, kiểm tra BIND9

```bash
# Tại thư mục gốc dự án
docker compose up -d internal-dns-server

docker compose ps internal-dns-server
docker logs --tail 100 internal-dns-server
```

Thử kiểm tra cú pháp cấu hình và zone bằng lệnh trong container:

```bash
docker exec internal-dns-server named-checkconf

docker exec internal-dns-server \
  named-checkzone cloud.local /etc/bind/db.cloud.local
```

Kỳ vọng:

- `docker compose ps` hiển thị service đang chạy (Running/Up).
- `named-checkconf` thoát với mã 0, không báo lỗi cú pháp.
- `named-checkzone` báo dạng `zone cloud.local/IN: loaded serial ...` và `OK`.
- Log không có lỗi `permission denied`, `zone not loaded`, `file not found` hoặc lỗi parse zone.

Nếu image đang dùng không đóng gói sẵn lệnh kiểm tra hoặc có khác biệt entrypoint, sử dụng container kiểm tra BIND9 khác/công cụ tương thích rồi ghi rõ cách kiểm thử thực tế. **Không đánh dấu hoàn thành nếu chưa chạy.**

## 7. Bước 5 - Kiểm thử các bản ghi DNS từ máy host

### 7.1. Bài kiểm thử cơ bản trong PDF

```bash
dig @127.0.0.1 -p 1053 web-frontend-server.cloud.local +short
```

**Kết quả kỳ vọng (theo cấu hình Word):**

```text
10.10.10.10
```

### 7.2. Kiểm thử đủ toàn bộ bản ghi A theo Word

```bash
dig @127.0.0.1 -p 1053 ns.cloud.local +short
dig @127.0.0.1 -p 1053 web-frontend-server.cloud.local +short
dig @127.0.0.1 -p 1053 app-backend.cloud.local +short
dig @127.0.0.1 -p 1053 minio.cloud.local +short
dig @127.0.0.1 -p 1053 keycloak.cloud.local +short
```

| Test | Kỳ vọng |
|---|---|
| `ns.cloud.local` | `127.0.0.1` |
| `web-frontend-server.cloud.local` | `10.10.10.10` |
| `app-backend.cloud.local` | `10.10.10.20` |
| `minio.cloud.local` | `10.10.10.30` |
| `keycloak.cloud.local` | `10.10.10.40` |

Để có thêm bằng chứng DNS trả lời từ BIND9, bỏ `+short` và xem `status: NOERROR`, phần `ANSWER SECTION`, server trả lời và TTL:

```bash
dig @127.0.0.1 -p 1053 keycloak.cloud.local A +noall +answer
```

**Đầu ra P4:** Ảnh Terminal hiển thị 5 câu lệnh và 5 kết quả IP tương ứng. Không khẳng định các web/app thực sự chạy tại IP đó chỉ dựa vào kết quả `dig`.

## 8. Bước 6 - Kiểm thử thay đổi zone và khởi động lại

Theo phần mở rộng của PDF: thêm `app-backend`, `minio`, `keycloak`; tài liệu Word đã **chốt sẵn toàn bộ IP**, vì vậy các bản ghi này được đưa trực tiếp vào file từ Bước 2.

Thực hành cập nhật/reload:

1. Ghi nhận file zone hiện tại, kết quả `dig` và SOA serial.
2. Thực hiện một chỉnh sửa zone có kiểm soát (nếu cần demo): ví dụ thay đổi serial từ `2026102401` thành `2026102402` mà **không đổi 5 giá trị A bắt buộc**.
3. Chạy `named-checkconf` và `named-checkzone`.
4. Restart service rồi truy vấn lại toàn bộ bản ghi.

```bash
docker compose restart internal-dns-server

dig @127.0.0.1 -p 1053 cloud.local SOA +noall +answer
dig @127.0.0.1 -p 1053 app-backend.cloud.local +short
dig @127.0.0.1 -p 1053 minio.cloud.local +short
dig @127.0.0.1 -p 1053 keycloak.cloud.local +short
```

**Đầu ra P5:** Ảnh/log trước-sau và lời giải thích SOA serial, DNS Zone, A record. Phần mở rộng DNS trong PDF: **thêm bản ghi và kiểm thử `dig`, tối đa 0,5 điểm**.

## 9. Bước 7 - Kiểm thử từ container trong `cloud-net`

Mục tiêu: chứng minh BIND9 có thể trả lời các truy vấn phát sinh **bên trong Docker Network**, không chỉ từ host qua cổng 1053.

```bash
# Dùng một container tiện ích tạm thời có lệnh dig
# Chú ý: cú pháp dùng DNS server theo Docker service name, port nội bộ 53.
docker run --rm --network cloud-net nicolaka/netshoot \
  dig @internal-dns-server -p 53 web-frontend-server.cloud.local +short
```

Kỳ vọng: `10.10.10.10`.

**Quan trọng:** Câu lệnh trên chủ động chỉ định DNS Server đích bằng `@internal-dns-server`. Việc đó **khác** với việc mọi container tự động sử dụng BIND9 làm DNS mặc định. Docker Compose mặc định có DNS nhúng để phân giải service names; muốn các container bình thường hỏi `cloud.local` từ BIND9 mà không ghi `@...` thì cần thêm thiết kế client DNS (ví dụ khai báo `dns:` và địa chỉ DNS có thể truy cập, hoặc cấu hình forwarder) do nhóm thống nhất.

### 9.1. Kiểm thử kết nối thật tới dịch vụ: KHÔNG tự động đạt

Các bản ghi theo Word là những **IP tĩnh quy ước**. Tuy nhiên Compose mẫu PDF không gán tĩnh các IP đó. Trước khi dùng hostname `*.cloud.local` để gọi Flask/MinIO/Keycloak, phối hợp người phụ trách Docker Network để xác minh:

```bash
docker network inspect cloud-net

docker inspect web-frontend-server \
  --format '{{json .NetworkSettings.Networks}}'

docker inspect application-backend-server \
  --format '{{json .NetworkSettings.Networks}}'
```

Nếu IP khác `10.10.10.x`, **không tự đổi bản ghi Word**. Đề nghị nhóm quyết định một trong hai phương án:

- **Phương án A - Demo DNS độc lập (đủ mục tiêu DNS trong tài liệu):** giữ 5 record cố định theo Word, chỉ minh chứng truy vấn DNS chính xác; giao tiếp thực tế giữa container dùng Docker service name.
- **Phương án B - Tích hợp DNS để kết nối thực:** nhóm cấu hình một subnet Docker phù hợp và IP tĩnh đã chốt cho 4 service Web/App/MinIO/Keycloak; tránh trùng subnet với mạng/VPN/EC2; xác định IP thật của DNS Server và cấu hình client DNS/forwarder. Việc này liên quan nhiều service, cần nhóm đồng ý trước khi chỉnh Compose.

Lưu ý thêm: `.local` cũng được dùng cho mDNS trên một số hệ điều hành; test `dig @127.0.0.1 -p 1053 ...` chỉ định máy chủ rõ ràng nên phù hợp với lab. Truy vấn hostname qua resolver hệ điều hành có thể xử lý khác.

## 10. Bước 8 - Kiểm thử trên AWS EC2 cùng nhóm

> DNS là dịch vụ **nội bộ**; không có yêu cầu phải mở cổng DNS công khai cho toàn Internet. Theo PDF, toàn bộ MiniCloud cần chạy trên AWS EC2, còn DNS vẫn phục vụ kiểm thử nội bộ.

- [ ] Nhận địa chỉ/SSH instance EC2 và quyền chạy Docker từ nhóm tích hợp.
- [ ] Xác minh có repo `Nhom<X>minicloud`, Compose chung và 3 file DNS đúng đường dẫn.
- [ ] Xác minh Docker Compose khởi chạy được `internal-dns-server` trên EC2.
- [ ] Chạy `named-checkconf` và `named-checkzone` trên EC2.
- [ ] Chạy `dig @127.0.0.1 -p 1053 ...` **ngay trên EC2 qua SSH** để tránh phải public UDP/1053.
- [ ] Lưu log demo EC2; bảo đảm Security Group không tùy tiện mở UDP/1053 ra `0.0.0.0/0`.

Nếu nhóm yêu cầu test DNS từ máy cá nhân qua Public IP, phải được nhóm phê duyệt cách giới hạn IP nguồn trong Security Group, đồng thời kiểm tra firewall của host và ACL BIND9. Không triển khai một open recursive resolver không kiểm soát trên Internet.

## 11. Kiểm thử lỗi và cách xử lý

| Triệu chứng | Nguyên nhân cần kiểm tra | Hướng xử lý |
|---|---|---|
| `connection timed out` khi `dig` | Container dừng, mapping UDP sai, firewall hoặc DNS không lắng nghe | `docker compose ps`, `docker logs`, kiểm tra `1053:53/udp` |
| Không nhận được A record | Sai tên hostname, zone chưa load, file mount sai | Xem `named-checkzone`, `ANSWER SECTION`, đúng tên `.cloud.local` |
| `SERVFAIL`/`zone not loaded` | Sai SOA/NS hoặc lỗi cú pháp BIND | `named-checkconf`, `named-checkzone`, đọc log |
| `permission denied`/`file not found` | Đường dẫn host hoặc quyền volume mount | Kiểm tra 3 file tồn tại trước khi `up`; mount `:ro` chính xác |
| `port is already allocated` | Host đã dùng UDP/1053 hoặc service bị chạy trùng | Kiểm tra container/service đang sử dụng port; chỉ có một DNS service trong Compose chung |
| DNS trả đúng IP nhưng HTTP không kết nối | IP `10.10.10.x` chưa thực sự gán cho Web/App | Đối chiếu IP container, dùng phương án A/B ở Bước 7 |
| Sau sửa file vẫn thấy giá trị cũ | Chưa restart/reload hoặc serial/caching | Tăng serial, check zone, restart, truy vấn trực tiếp BIND9 |
| Container trên EC2 không chạy | Docker, port, mount, quyền, kernel/network | Kiểm tra log/Compose và file tồn tại trên EC2 |

## 12. Danh sách ảnh/log phải thu thập để nộp báo cáo

- [ ] Ảnh cấu trúc thư mục `internal-dns-server/`.
- [ ] Ảnh 3 file cấu hình (đặc biệt `db.cloud.local` đủ 5 bản ghi).
- [ ] Ảnh đoạn Compose DNS và cấu hình `cloud-net`.
- [ ] Ảnh `docker compose ps` cho `internal-dns-server` đang chạy.
- [ ] Ảnh `named-checkzone cloud.local ...` thành công.
- [ ] Ảnh kiểm thử `dig` Web Server cơ bản: `10.10.10.10`.
- [ ] Ảnh kiểm thử `dig` 4 tên còn lại và kết quả.
- [ ] Ảnh/log sau khi cập nhật serial/restart và test lại.
- [ ] Ảnh `dig` từ container trong `cloud-net`.
- [ ] Ảnh/log chạy DNS trên AWS EC2 (nếu nhóm đã triển khai).

**Gợi ý vị trí trong báo cáo:** Chương 2 (vai trò DNS trong sơ đồ hệ thống), Chương 3 (BIND9 files + Compose), Chương 4 (lệnh, kết quả và ảnh kiểm thử), Chương 5 (ưu điểm/hạn chế của static A records, hướng mở rộng service discovery), Phụ lục (log/trích đoạn cấu hình).

## 13. Nội dung cần bàn giao cho các thành viên khác

### 13.1. Hợp đồng tích hợp (integration contract)

```text
Docker network       : cloud-net
Service/container    : internal-dns-server
Docker image         : internetsystemsconsortium/bind9:9.18
Host -> container    : UDP 1053 -> UDP 53
Authoritative zone   : cloud.local
Zone file            : internal-dns-server/db.cloud.local
Config files         : named.conf.options, named.conf.local
Compose             : service internal-dns-server trong docker-compose.yml chung
```

```text
ns.cloud.local                  -> 127.0.0.1
web-frontend-server.cloud.local -> 10.10.10.10
app-backend.cloud.local         -> 10.10.10.20
minio.cloud.local               -> 10.10.10.30
keycloak.cloud.local            -> 10.10.10.40
```

### 13.2. Tài liệu bàn giao

- [ ] Thư mục `internal-dns-server/` chứa 3 file đã kiểm tra.
- [ ] Commit/PR thêm service vào Compose chung (hoặc snippet để người phụ trách tích hợp ghép).
- [ ] Hướng dẫn `docker compose up -d internal-dns-server` và `dig`.
- [ ] Kết quả kiểm thử, ảnh minh chứng và log.
- [ ] Thông báo rõ: record IP cố định theo Word **chưa đủ** bảo đảm IP thực tế Docker khớp.
- [ ] Thống nhất với nhóm triển khai về mô hình IP (Demo A hay Tích hợp B) và quyền truy vấn DNS trên EC2.

## 14. Kịch bản demo trước giảng viên (2-4 phút)

1. **Giới thiệu:** DNS Server số 6; BIND9 mô phỏng DNS zone `cloud.local` trong MiniCloud.
2. **Minh họa cấu hình:** Mở `db.cloud.local` cho thấy đủ 5 A records chốt theo Word.
3. **Minh họa Docker:** `docker compose ps internal-dns-server` và `docker network inspect cloud-net`.
4. **Minh họa kiểm tra:** `named-checkzone` trả `OK`.
5. **Minh họa chính:** `dig @127.0.0.1 -p 1053 web-frontend-server.cloud.local +short` trả `10.10.10.10`.
6. **Minh họa mở rộng:** `dig` cho `app-backend`, `minio`, `keycloak`, lần lượt trả `10.10.10.20`, `10.10.10.30`, `10.10.10.40`.
7. **Tổng kết:** Giải thích khác nhau giữa bản ghi DNS tĩnh, IP container thực tế và DNS tích hợp sẵn của Docker.

## 15. Checklist nghiệm thu cuối cùng

### Mức cơ bản - bắt buộc

- [ ] Đúng tên thư mục, image, container, network, port theo Word.
- [ ] BIND9 khởi chạy và tải thành công zone `cloud.local`.
- [ ] `dig` bản ghi Web trả `10.10.10.10`.
- [ ] Có ảnh cấu hình và kết quả demo.

### Mức mở rộng - DNS (tối đa 0,5 điểm theo PDF)

- [ ] Bản ghi `app-backend.cloud.local -> 10.10.10.20`.
- [ ] Bản ghi `minio.cloud.local -> 10.10.10.30`.
- [ ] Bản ghi `keycloak.cloud.local -> 10.10.10.40`.
- [ ] Sau restart vẫn phân giải thành công cả 3 tên miền.
- [ ] Trình bày ý nghĩa Zone File, SOA, NS, A record, TTL và DNS caching.

### Tích hợp nhóm/AWS

- [ ] DNS service đã được ghép vào Compose chính thức của nhóm (không chạy trùng).
- [ ] Kết quả kiểm thử `dig` từ host và trong `cloud-net`.
- [ ] Có kết quả EC2 khi nhóm triển khai tổng thể.
- [ ] Có xác nhận mô hình IP/DNS thực tế trước khi tuyên bố các ứng dụng gọi nhau bằng `*.cloud.local`.

---

## 16. Các điểm cần xác nhận với nhóm (không tự thay quy ước)

1. **`Nhom<X>minicloud`:** giá trị `<X>` là số nhóm nào? Tên thư mục gốc phải theo nhóm thống nhất.
2. **Network `cloud-net`:** nhóm dùng network do Compose tạo, hay external network đã có?
3. **Các IP `10.10.10.10/20/30/40`:** có được gán thực cho bốn container tương ứng hay chỉ là các IP trong DNS lab?
4. **Bản ghi `ns.cloud.local = 127.0.0.1`:** giữ nguyên phục vụ kiểm thử quy ước; nếu làm DNS client thực cần chọn IP BIND9 mà client có thể đến được.
5. **Triển khai EC2:** ai phụ trách ghép Compose, xử lý Security Group và thu thập log/ảnh? DNS không nên mở recursive resolver ra công cộng.

> **Tổng kết:** Hoàn thành service Internal DNS nghĩa là có **BIND9 chạy được, trả đúng 5 A records chuẩn nhóm qua `dig`, tích hợp với Docker Compose `cloud-net`, có bằng chứng kiểm thử local và EC2**. Không đồng nhất "trả được IP" với "container đang chạy tại IP đó" khi chưa kiểm tra Docker Network thực tế.
