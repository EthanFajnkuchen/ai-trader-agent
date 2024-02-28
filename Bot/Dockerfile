# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the current directory contents into the container at /usr/src/app
COPY . .

# Install any needed packages specified directly
RUN pip install pyTelegramBotAPI python-dotenv requests

# Make port 8000 available to the world outside this container
EXPOSE 80
# Run bot.py when the container launches
CMD ["python", "Bot/bot.py"]
