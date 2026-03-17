FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE ${PORT:-8080}
CMD gunicorn -b 0.0.0.0:${PORT:-8080} -w 2 --timeout 30 app:app
