FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev build-essential pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FLASK_APP=run.py

RUN mkdir -p /app/data
VOLUME ["/app/data"]

EXPOSE 5000

RUN chmod +x entrypoint.sh
ENTRYPOINT ["./entrypoint.sh"]
