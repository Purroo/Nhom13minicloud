FROM nginx:stable
RUN rm -f /etc/nginx/conf.d/default.conf
COPY conf.default /etc/nginx/conf.d/default.conf
COPY html/ /usr/share/nginx/html/
# Normalize the Prometheus exposition file in the image. A Windows CRLF makes
# Prometheus parse the metric type as "gauge\r" and reject the web target.
RUN sed -i 's/\r$//' /usr/share/nginx/html/metrics.txt \
    && chmod -R 755 /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -fsS http://localhost/blog/ > /dev/null || exit 1
CMD ["nginx", "-g", "daemon off;"]
