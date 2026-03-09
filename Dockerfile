# Base image — Python 3.11 on a lightweight Linux OS
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy requirements first — this lets Docker cache the pip install layer
# so rebuilds are faster when only your code changes
COPY requirements.txt .

# Install all Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your project into the container
COPY . .

# Tell Cloud Run which port your app listens on
EXPOSE 8080

# Command that starts the server when the container runs
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]