# Use a base image that includes necessary tools, or install them
FROM python:3.9-slim-buster

# Set environment variables for non-interactive installation
ENV DEBIAN_FRONTEND=noninteractive

# Install Chromium and its dependencies
# These dependencies are crucial for Chromium to run headless
RUN apt-get update && apt-get install -y \
    chromium-driver \
    chromium \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libexpat1 \
    libfontconfig1 \
    libgbm-dev \
    libgdk-pixbuf2.0-0 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libstdc++6 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    xdg-utils \
    # Clean up after installation to reduce image size
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory inside the container
WORKDIR /app

# Copy requirements.txt and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Set environment variables for Chromium/ChromeDriver
# These might be needed to help Selenium find the browser and driver
ENV CHROME_BIN=/usr/bin/chromium-browser
ENV CHROMEDRIVER_PATH=/usr/bin/chromium-driver
# Ensure /usr/bin is in PATH for executable
ENV PATH="${PATH}:/usr/bin"

# Command to run your application using Gunicorn
# This matches your Procfile, but is now inside the Dockerfile
CMD ["gunicorn", "main:app", "--timeout", "600", "-b", "0.0.0.0:5000"]
