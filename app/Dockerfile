FROM python:3.12-alpine3.19

RUN adduser -D appuser

WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip setuptools && pip install --no-cache-dir -r requirements.txt

COPY app.py .

USER appuser
EXPOSE 8080

CMD ["python", "app.py"]
