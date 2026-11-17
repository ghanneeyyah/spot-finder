FROM python:3.13-slim

# Prevent Python from writing .pyc files and enable unbuffered CLI logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app

# Create a dedicated non-root user and group for security
RUN addgroup --system fastapi && adduser --system --ingroup fastapi fastapi

# Copy only the dependencies file first to maximize Docker layer caching
COPY requirements.txt .

# Install dependencies without storing cache to keep the image size minimal
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Ensure the non-root user owns the application directory
RUN chown -R fastapi:fastapi /app

# Drop root privileges
USER fastapi

# Expose the port Uvicorn will run on
EXPOSE 8000

# Execute Uvicorn, pointing to the app instance in app/main.py
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]