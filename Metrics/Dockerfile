FROM python:3.11-slim

WORKDIR /app

COPY metrics-service.py ./

RUN pip install --no-cache-dir flask pymongo

CMD ["python", "metrics-service.py"]
