FROM golang:1.24.8-alpine AS builder

ARG MINIO_COMMIT=7aac2a2c5b7c882e68c1ce017d8256be2feea27f
RUN apk add --no-cache git ca-certificates
WORKDIR /src
RUN git init . \
    && git remote add origin https://github.com/minio/minio.git \
    && git fetch --depth=1 origin "${MINIO_COMMIT}" \
    && git checkout --detach FETCH_HEAD \
    && test "$(git rev-parse HEAD)" = "${MINIO_COMMIT}"
RUN --mount=type=cache,target=/go/pkg/mod go mod download
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 go build -tags kqueue -trimpath -ldflags="-s -w" -o /out/minio .

FROM alpine:3.22
RUN apk add --no-cache ca-certificates curl tzdata
COPY --from=builder /out/minio /usr/local/bin/minio
COPY --from=builder /src/LICENSE /src/CREDITS /licenses/
LABEL org.opencontainers.image.source="https://github.com/minio/minio" \
      org.opencontainers.image.revision="7aac2a2c5b7c882e68c1ce017d8256be2feea27f" \
      org.opencontainers.image.title="Nhom13 MinIO lab build"
EXPOSE 9000 9001
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=6 \
    CMD curl -fsS http://localhost:9000/minio/health/live || exit 1
ENTRYPOINT ["/usr/local/bin/minio"]
CMD ["server", "/data", "--console-address", ":9001"]
