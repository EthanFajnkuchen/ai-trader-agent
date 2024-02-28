# Trader Agent Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    gcc \
    libc6-dev \
    make \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY ./TraderAgent /app

RUN pip install fastapi uvicorn python-dotenv redis alpaca-trade-api yfinance lumibot datetime timedelta

EXPOSE 81

CMD ["uvicorn", "trader_agent:app", "--host", "0.0.0.0", "--port", "81"]
