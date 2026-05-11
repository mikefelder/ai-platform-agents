FROM python:3.14-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY main.py agents.yaml agent.yaml ./
COPY tools/ tools/

EXPOSE 8088

CMD ["python", "main.py"]
