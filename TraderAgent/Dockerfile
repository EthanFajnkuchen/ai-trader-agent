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


COPY TraderAgent .
# Install any needed packages specified directly
RUN pip install --no-cache-dir --upgrade -r requirements.txt


EXPOSE 81

CMD ["uvicorn", "trader_agent:app", "--host", "0.0.0.0", "--port", "81", "--reload"]