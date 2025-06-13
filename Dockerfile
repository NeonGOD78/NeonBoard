FROM python:3.12-slim

WORKDIR /app
COPY exporter.py .
RUN pip install flask requests prometheus_client

EXPOSE 9814
CMD ["python", "exporter.py"]
