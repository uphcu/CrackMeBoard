FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libmariadb-dev-compat && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m -s /bin/bash crackme && chown -R crackme:crackme /app
USER crackme

EXPOSE 8000

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "app:create_app()"]