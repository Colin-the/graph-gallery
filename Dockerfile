FROM python:3.12-slim

WORKDIR /app

# Install Flask
RUN pip install --no-cache-dir flask gunicorn

# Copy app source
COPY app/ ./app/
COPY graphs_manifest.json .

# Copy all generated graph images (populated by extract/render scripts before build)
COPY static/graphs/ ./static/graphs/

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "60", "app.server:app"]
