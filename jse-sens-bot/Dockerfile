# Dockerfile at the root of the project
FROM python:3.12.0-slim
ENV PYTHONUNBUFFERED=1

# Install necessary packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    firefox-esr \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*


# Install geckodriver
RUN wget https://github.com/mozilla/geckodriver/releases/download/v0.31.0/geckodriver-v0.31.0-linux64.tar.gz \
    && tar -xvzf geckodriver-v0.31.0-linux64.tar.gz \
    && chmod +x geckodriver \
    && mv geckodriver /usr/local/bin/ \
    && rm geckodriver-v0.31.0-linux64.tar.gz

# Set up a working directory
WORKDIR /app

# Copy requirementsLin and install them
COPY requirementsLin.txt /app/requirementsLin.txt
RUN pip install --no-cache-dir -r requirementsLin.txt

# Copy the rest of the application code
COPY ./ /app/

# Expose the FastAPI port
EXPOSE 8000

# Default command to run the FastAPI app
# CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
