# PLAN — MỞ RỘNG 6: INTERNAL DNS SERVER

**Dự án:** MyMiniCloud — Nhóm 13
**Service:** `internal-dns-server` (BIND9 9.18), mạng `cloud-net`
**Trạng thái:** Đã thực thi giai đoạn A, B, C, D ngày 25/10/2026; 12/12 test case đạt (mục 7). Còn lại: chụp minh chứng (mục 8).

## 0. Yêu cầu và tiêu chí hoàn thành

Thêm vào zone `cloud.local` (file `db.cloud.local`) bản ghi `app-backend.cloud.local IN A 10.10.10.20`, test bằng `dig`. Bổ sung `minio.cloud.local` và `keycloak.cloud.local`, restart container DNS rồi kiểm tra lại. Cần hiểu zone file, caching DNS và cách container dùng DNS nội bộ để gọi nhau. Đề bài không nêu IP của `minio` và `keycloak`, nên dùng IP quy ước của nhóm (`10.10.10.30`, `10.10.10.40`).

- [ ] `db.cloud.local` có đủ 3 bản ghi A: `app-backend`, `minio`, `keycloak`.
- [ ] `named-checkzone` báo OK, `dig` trả đúng 3 IP.
- [ ] Sau `docker compose restart internal-dns-server`, container healthy và `dig` vẫn đúng.
- [ ] Có minh chứng quy trình thêm bản ghi (trước: NXDOMAIN, sau: đúng IP).
- [ ] Có minh chứng caching (TTL giảm dần) và cách container dùng DNS nội bộ.
- [ ] Tài liệu của service khớp thực tế.

## 1. Hiện trạng (đã kiểm tra, chỉ đọc)

| Hạng mục | Kết quả |
|---|---|
| Container | `internal-dns-server`, healthy, `1053->53/udp`, IP `172.19.0.8` (Docker cấp động, đổi khi dựng lại) |
| Image | Compose `build: ./internal-dns-server` thành `nhom13minicloud/bind9:dev` (nền `bind9:9.18`), vẫn bind-mount 4 file `:ro` |
| Zone | `cloud.local`, serial `2026102401`, `$TTL 1H`, NS `ns.cloud.local` |
| 3 bản ghi của đề | **Đã có sẵn** trong `db.cloud.local` (commit `aaac520`); `dig` từ host trả `10.10.10.20`, `.30`, `.40` |
| File host và container | `md5sum` của `db.cloud.local` khớp nhau |
| `rndc` | Không dùng được (thiếu `rndc.key`), nên áp dụng thay đổi bằng restart |
| Caching | Tên ngoài (`example.com`): TTL giảm `191, 188, 185` giữa các lần hỏi. Tên nội bộ: cờ `aa`, TTL luôn `3600` |
| Resolver của backend | `127.0.0.11` (DNS nhúng Docker): `authentication-identity-server` ra `172.19.0.5`, `app-backend.cloud.local` lỗi `Try again` |
| Container trỏ `--dns` tới BIND9 | Phân giải được cả `app-backend.cloud.local` (`10.10.10.20`) lẫn tên service Docker |
| IP thật trong `cloud-net` | `172.19.0.x`, khác `10.10.10.x` của zone |
| Dùng `*.cloud.local` | Grep trong `docker-compose.yml`, `app.py`, `nginx.conf`, `prometheus.yml`, `*.env` chỉ thấy dòng mount file zone; không service nào gọi nhau bằng tên này |

**Kết luận từ hiện trạng:** ba bản ghi mà đề yêu cầu thêm đã có trong zone. Phần còn thiếu là chứng minh quy trình (bản ghi chưa có thì NXDOMAIN, thêm vào thì phân giải được), phần restart, phần caching, và tài liệu. Quan trọng nhất: `docs/06-internal-dns.md` ở gốc repo vẫn ghi 3 file cấu hình "trống 0 byte", sai so với thực tế.

## 2. Quyết định thiết kế

| Vấn đề | Quyết định | Lý do |
|---|---|---|
| Bản ghi đã có sẵn | Không sửa 3 giá trị `10.10.10.20/30/40`. Demo thêm bản ghi bằng một bản ghi tạm (`demo-extend`) rồi gỡ | Đề yêu cầu "thêm bản ghi". Dùng tên riêng nên không động tới giá trị nhóm đã chốt |
| IP `10.10.10.x` khác IP thật `172.19.0.x` | Giữ Phương án A đã chọn trong `docs/README.md` của service: DNS demo độc lập, service gọi nhau bằng tên Docker | Đổi subnet hoặc gán IP tĩnh ảnh hưởng nhiều service, ngoài phạm vi đề |
| Áp dụng thay đổi zone | Sửa file, tăng SOA serial, `named-checkzone`, `docker compose restart` | `rndc reload` không dùng được; đề yêu cầu restart |
| Phần "container dùng DNS nội bộ" | Demo bằng container tạm `--dns <IP BIND9>`; không sửa `docker-compose.yml` | Khai báo `dns:` cho service thật sẽ làm đổi cách phân giải của backend, gateway, Keycloak. Phải hỏi nhóm trước |
| Bản ghi demo | Xóa sau khi demo, tăng serial lần nữa | Zone cuối cùng chỉ còn 5 bản ghi chuẩn của nhóm |

## 3. Giai đoạn A — Kiểm tra trước khi sửa

```bash
cd /Users/thanhtu/HK1_26_27/c-c/project/Nhom13minicloud
docker compose ps internal-dns-server
docker exec internal-dns-server named-checkzone cloud.local /etc/bind/db.cloud.local
for n in app-backend minio keycloak; do dig @127.0.0.1 -p 1053 $n.cloud.local +short; done
dig @127.0.0.1 -p 1053 cloud.local SOA +noall +answer     # ghi lại serial hiện tại
git status --short internal-dns-server                    # nên sạch
```

Kỳ vọng: healthy, zone OK, ba IP đúng, serial `2026102401`.

## 4. Giai đoạn B — Thêm bản ghi và restart

**B1. Trước khi thêm** (chứng minh tên chưa tồn tại):

```bash
dig @127.0.0.1 -p 1053 demo-extend.cloud.local +noall +comments | grep status    # NXDOMAIN
```

**B2. Sửa `db.cloud.local`.** Thêm bản ghi demo và tăng serial `2026102401` lên `2026102402`:

```dns
demo-extend           IN A   10.10.10.99
```

**B3. Kiểm tra và áp dụng:**

```bash
docker exec internal-dns-server named-checkzone cloud.local /etc/bind/db.cloud.local
docker compose restart internal-dns-server
docker compose ps internal-dns-server                    # đợi healthy
```

**B4. Kiểm tra lại toàn bộ:**

```bash
for n in demo-extend app-backend minio keycloak web-frontend-server ns; do
  printf "%-22s " $n.cloud.local; dig @127.0.0.1 -p 1053 $n.cloud.local +short
done
dig @127.0.0.1 -p 1053 cloud.local SOA +noall +answer    # serial 2026102402
```

Kỳ vọng: `demo-extend` ra `10.10.10.99`, ba bản ghi của đề và hai bản ghi còn lại không đổi.

**B5. Dọn bản ghi demo.** Xóa dòng `demo-extend`, tăng serial lên `2026102403`, chạy lại `named-checkzone`, restart, rồi xác nhận `demo-extend` trả NXDOMAIN và 5 bản ghi chuẩn còn đúng.

Nếu muốn giữ bản ghi demo trong báo cáo thì chụp ảnh ở B4 trước khi dọn. Không commit bản ghi demo.

## 5. Giai đoạn C — Caching và container dùng DNS nội bộ

**C1. Caching.** Hỏi cùng một tên ngoài 3 lần, cách nhau vài giây:

```bash
for i in 1 2 3; do dig @127.0.0.1 -p 1053 example.com A +time=10 +tries=1 +noall +answer; sleep 3; done
```

Kỳ vọng: TTL giảm dần (đã thấy `191, 188, 185`), nghĩa là BIND9 trả từ cache sau lần đầu.

Với tên trong zone `cloud.local`, câu trả lời có cờ `aa` (authoritative) và TTL luôn `3600`, vì BIND9 là nguồn gốc dữ liệu, không phải cache. Giá trị `3600` đến từ `$TTL 1H`. Client hoặc resolver trung gian mới cache tên này tối đa 1 giờ. Tên không tồn tại được cache theo trường cuối của SOA (`1H`).

**C2. Container hỏi DNS nội bộ.**

```bash
DNSIP=$(docker inspect internal-dns-server --format '{{(index .NetworkSettings.Networks "cloud-net").IPAddress}}')
docker run --rm --network cloud-net nicolaka/netshoot dig @internal-dns-server app-backend.cloud.local +short
docker run --rm --network cloud-net --dns "$DNSIP" nicolaka/netshoot dig app-backend.cloud.local +short
docker exec application-backend-server python -c 'import socket; print(socket.gethostbyname("app-backend.cloud.local"))'
```

Kỳ vọng: hai lệnh đầu trả `10.10.10.20`; lệnh thứ ba lỗi `Try again`, vì backend dùng DNS nhúng của Docker (`127.0.0.11`) chứ không dùng BIND9.

Từ kết quả này ghi vào tài liệu ba cách container tới được BIND9:
1. Chỉ định tường minh: `dig @internal-dns-server`.
2. Cấu hình `dns:` hoặc `--dns` cho container, trỏ tới IP của BIND9. Container vẫn phân giải được tên service Docker, vì DNS nhúng của Docker nhận forward.
3. Mặc định: container chỉ thấy DNS nhúng Docker, không thấy zone `cloud.local`.

**C3. Hạn chế cần nêu trong báo cáo.**
- `10.10.10.x` khác IP thật `172.19.0.x`, nên phân giải được tên không có nghĩa kết nối được dịch vụ.
- `ns.cloud.local = 127.0.0.1` là loopback của máy đang hỏi, không dùng được như địa chỉ của BIND9 cho container khác.
- IP của container BIND9 do Docker cấp, có thể đổi khi dựng lại mạng.
- `recursion yes` với `allow-query { any; }` chỉ chấp nhận được ở local. Nếu mở UDP/1053 ra ngoài (ví dụ trên EC2) sẽ thành open resolver. Cần giới hạn ACL hoặc Security Group.

## 6. Giai đoạn D — Cập nhật tài liệu

- [ ] Sửa `docs/06-internal-dns.md` (gốc repo): mục 4 đang ghi "3 file trống, chưa hoàn thiện", mục 3 ghi image và 3 mount cũ. Cập nhật theo hiện trạng: 4 file, `build: ./internal-dns-server`, zone có đủ 5 bản ghi.
- [ ] Thêm vào `internal-dns-server/docs/README.md` một mục "Mở rộng 6": kết quả B và C, bảng ba cách container dùng DNS, các hạn chế ở C3.
- [ ] Ghi ngày chạy và kết quả vào bảng nghiệm thu mục 7.

## 7. Bảng nghiệm thu

| ID | Kịch bản | Kỳ vọng | Trạng thái |
|---|---|---|---|
| DNS-01 | `named-checkzone` trước và sau khi sửa | OK | Đạt (serial `01`, `02`, `03`) |
| DNS-02 | `demo-extend` trước khi thêm | NXDOMAIN | Đạt |
| DNS-03 | `demo-extend` sau khi thêm và restart | `10.10.10.99` | Đạt |
| DNS-04 | `app-backend.cloud.local` | `10.10.10.20` | Đạt (trước, trong, sau khi sửa) |
| DNS-05 | `minio.cloud.local` | `10.10.10.30` | Đạt |
| DNS-06 | `keycloak.cloud.local` | `10.10.10.40` | Đạt |
| DNS-07 | Sau restart: container healthy, 3 tên trên vẫn đúng | Đúng | Đạt (2 lần restart) |
| DNS-08 | SOA serial tăng sau mỗi lần sửa | `...02`, rồi `...03` | Đạt |
| DNS-09 | Zone cuối chỉ còn 5 bản ghi chuẩn, `demo-extend` NXDOMAIN | Đúng | Đạt |
| DNS-10 | Caching: TTL tên ngoài giảm dần; tên nội bộ `aa` và TTL 3600 | Đúng | Đạt (`165, 161, 157`; `aa`, `3600`) |
| DNS-11 | Container tạm dùng `@internal-dns-server` và `--dns` | `10.10.10.20` | Đạt |
| DNS-12 | Backend phân giải `app-backend.cloud.local` bằng DNS mặc định | Lỗi (hành vi đúng) | Đạt (`Try again`) |

## 8. Minh chứng cần chụp

- [ ] `01-zone-file.png`: `db.cloud.local` với 5 bản ghi chuẩn (và dòng demo nếu chụp ở B4)
- [ ] `02-nxdomain-before.png`: B1
- [ ] `03-checkzone-restart.png`: `named-checkzone` OK và `docker compose ps` healthy sau restart
- [ ] `04-dig-after-restart.png`: B4, đủ các tên và SOA serial mới
- [ ] `05-cache-ttl.png`: C1, TTL giảm dần
- [ ] `06-container-dns.png`: C2, ba lệnh và kết quả
- [ ] `07-cleanup.png`: B5, `demo-extend` NXDOMAIN, 5 bản ghi chuẩn còn nguyên

## 9. Giải thích kiến thức

- **Zone file:** file văn bản chứa dữ liệu authoritative của zone (SOA, NS, A). BIND9 đọc file này khi khởi động hoặc reload. Sửa file mà không tăng serial và không reload thì BIND9 không biết có thay đổi.
- **SOA serial:** số phiên bản của zone. Server phụ (secondary) so serial để quyết định có tải lại zone không. Lab chỉ có một master nên serial chủ yếu để theo dõi thay đổi.
- **Caching:** resolver lưu câu trả lời trong thời gian TTL. TTL giảm dần cho thấy câu trả lời đến từ cache. Server authoritative không cache dữ liệu zone của chính nó.
- **Container gọi nhau:** mặc định qua DNS nhúng Docker (`127.0.0.11`), phân giải tên service như `authentication-identity-server`. BIND9 chỉ phục vụ `cloud.local` khi được chỉ định hoặc cấu hình làm DNS của container.

## 10. Phạm vi và rủi ro

- Chỉ sửa `internal-dns-server/db.cloud.local` tạm thời trong lúc demo; trạng thái cuối trùng nội dung hiện tại trừ serial (`2026102403`).
- Không sửa `docker-compose.yml`, `named.conf*`, Dockerfile.
- Restart container DNS chỉ làm gián đoạn phân giải vài giây; không service nào đang dùng `*.cloud.local`.
- Không chạm vào `docker compose down -v` hay xóa volume.
- Chưa kiểm thử trên EC2.
