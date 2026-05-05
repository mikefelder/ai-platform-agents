FROM python:3.12-slim

WORKDIR /app

COPY . user_agent/
WORKDIR /app/user_agent

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8088

CMD ["python", "main.py"]
