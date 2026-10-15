FROM python:3.13-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
# Sin privilegios de administrador dentro del contenedor.
RUN useradd --create-home --uid 10001 api
USER api
ENV PORT=8080 PRODUCCION=1
# --proxy-headers: detrás de Cloud Run / Railway / Render la API ve la IP real (el límite de invitados por red la usa).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
