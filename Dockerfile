FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy API source code
COPY src/api ./src/api

# Copy trained models and preprocessors
COPY models ./models

# Copy configs if they exist
COPY configs ./configs

# Install dependencies
RUN pip install --no-cache-dir -r src/api/requirements.txt

# Set the working directory to the API folder for execution
WORKDIR /app/src/api

# Expose port
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]