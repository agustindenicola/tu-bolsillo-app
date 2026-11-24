FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TUBOLSILLO_DATA=/data \
    TUBOLSILLO_HTTPS=1 \
    PORT=8080

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# navegador invisible para las fuentes que arman las promos con JavaScript (por ejemplo, Banco Ciudad)
RUN pip install --no-cache-dir playwright && playwright install --with-deps chromium
COPY run.py .
COPY tubolsillo ./tubolsillo

# los datos (base, claves, fotos subidas) viven en /data: montá ahí un volumen para no perderlos
VOLUME ["/data"]
EXPOSE 8080
CMD ["python", "run.py"]
