FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY db_metrics_exporter.py .

EXPOSE 9001

CMD ["python", "db_metrics_exporter.py"]
