# Use Python base image
FROM python:3.9-slim

# Set working directory inside container
WORKDIR /app

# Copy dependency file first
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Expose the Flask port
EXPOSE 8080

# Run the Flask app
CMD ["python", "app.py"]
