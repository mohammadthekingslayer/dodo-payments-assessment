FROM python:3.12-alpine3.22

RUN apk update && apk upgrade --no-cache
RUN adduser -D appuser

WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip setuptools && pip install --no-cache-dir -r requirements.txt

COPY app.py .

USER appuser
EXPOSE 8080

CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:app"]
