# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# First, copy only the requirements.txt file and install Python dependencies
COPY BotSub/requirements.txt .
RUN pip install --upgrade -r requirements.txt

# After pip install, copy the rest of your application
COPY BotSub .
COPY .env .

# Make port 80 available to the world outside this container
EXPOSE 82

# Run bot.py when the container launches
CMD ["python", "subscriber.py"]
