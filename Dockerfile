FROM python:3.11-slim

WORKDIR /app

COPY server.py .
COPY index.html .

RUN mkdir -p /app/data

EXPOSE 7331

CMD ["python3", "-u", "server.py"]
