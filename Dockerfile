# Backend
FROM python:3.12-slim as backend

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create necessary directories
RUN mkdir -p images output logs

EXPOSE 5000

CMD ["python", "app.py"]
