FROM python:3.9-slim AS  builder
WORKDIR /app

COPY ./app/requirements.txt .

RUN pip install -r requirements.txt \
    && rm requirements.txt

Run pip install boto3

COPY ./app/ .
FROM builder

WORKDIR /app

COPY --from=builder /app .

EXPOSE 8000

CMD gunicorn --bind 0.0.0.0:8000 wsgi:app
