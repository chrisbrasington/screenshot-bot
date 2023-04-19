# Use the official Python image as the base image
FROM python:3.8

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    unzip \
    firefox-esr \
    iproute2

# Set the working directory to /app
WORKDIR /app

# Install cron
RUN apt-get update && apt-get install -y cron

# Download and install Geckodriver
RUN wget https://github.com/mozilla/geckodriver/releases/download/v0.30.0/geckodriver-v0.30.0-linux64.tar.gz && \
    tar -xvzf geckodriver-v0.30.0-linux64.tar.gz && \
    chmod +x geckodriver && \
    cp geckodriver /usr/local/bin \
    cp geckodriver /usr/bin 

# Add network throttling rule
# RUN tc qdisc add dev eth0 root tbf rate 1mbit burst 32kbit latency 400ms

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --trusted-host pypi.python.org -r requirements.txt

# Make port 80 available to the world outside this container
EXPOSE 80

# Set environment variables
ENV DISPLAY=:99
ENV MOZ_HEADLESS=1

# Add /usr/local/bin to the PATH
ENV PATH="/usr/local/bin:${PATH}"

# Run bot.py when the container launches
# CMD ["python", "bot.py"]

# run every 5 minutes
# CMD while true; do python bot.py; sleep 300; done

# Copy the cron job file to the proper location
COPY cronjob /etc/cron.d/cronjob

# Apply proper permissions to the cron job file
RUN chmod 0644 /etc/cron.d/cronjob

# Add the log file for the cron job
RUN touch /var/log/cron.log

# Run the command on container startup and
# Start the cron service in the background and tail the log file
CMD python bot.py && service cron start && tail -f /var/log/cron.log
