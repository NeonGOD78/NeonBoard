FROM python:3.12-slim

WORKDIR /app

COPY exporter.py .

# Install dependencies
RUN pip install flask requests prometheus_client psutil

# Brug miljøvariabel til port – Docker EXPOSE er ikke dynamisk, men vi eksponerer alligevel standardport
EXPOSE 9861

# Start exporter
CMD ["python", "exporter.py"]
