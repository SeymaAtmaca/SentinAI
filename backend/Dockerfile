# 1. Aşama: Builder
FROM python:3.11-slim AS builder 

# Derleme için gerekli olabilecek paketleri ekleyelim (Opsiyonel ama önerilir)
RUN apt-get update && apt-get install -y --no-install-recommends gcc python3-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /build 
COPY requirements.txt . 

# --prefix yerine doğrudan sisteme yükleyip sonra o klasörü kopyalamak daha sağlıklıdır
# veya --user flag'i kullanılabilir. İşte en temiz yol:
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# 2. Aşama: Final
FROM python:3.11-slim 
LABEL maintainer="ModelGuardian AI Team"

# Python'un kütüphaneleri bulabilmesi için PYTHONPATH ve PATH ayarı
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PATH="/usr/local/bin:$PATH"

WORKDIR /app 

# Builder'dan gelen dosyaları kopyalıyoruz
# /install altındaki her şeyi direkt /usr/local içine atarak sistem kütüphanesi gibi davranmasını sağlıyoruz
COPY --from=builder /install /usr/local

# Kullanıcı ve dizin işlemleri
RUN groupadd -r appgroup && useradd -r -g appgroup -d /app -s /sbin/nologin appuser \ 
    && mkdir -p /app/src /app/logs && chown -R appuser:appgroup /app 

# Healthcheck için curl gerekli (slim imajlarda genelde yüklü gelmez)
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

USER appuser 

COPY --chown=appuser:appgroup src/ /app/src/ 
COPY --chown=appuser:appgroup requirements.txt /app/ 

EXPOSE 8000 

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1 

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]