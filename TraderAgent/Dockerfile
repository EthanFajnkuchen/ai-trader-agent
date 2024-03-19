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


# First, copy only the requirements.txt file and install Python dependencies
COPY TraderAgent/requirements.txt .
RUN pip install --upgrade -r requirements.txt

# After pip install, copy the rest of your application
COPY TraderAgent .

EXPOSE 81

CMD ["uvicorn", "trader_agent:app", "--host", "0.0.0.0", "--port", "81", "--reload"]