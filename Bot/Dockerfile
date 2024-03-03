# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /usr/src/app

COPY Bot .

# Install any needed packages specified directly
RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY .env .

# Make port 8000 available to the world outside this container
EXPOSE 80
# Run bot.py when the container launches
CMD ["python", "bot.py"]