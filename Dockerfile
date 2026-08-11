# Aegis Engineer — runtime image (local solve / CLI)
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir -e ".[dev]"

ENTRYPOINT ["aegis"]
CMD ["doctor"]
