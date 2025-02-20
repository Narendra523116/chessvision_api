FROM python:3.13.1

# Set the working directory in the container
WORKDIR /app

COPY requirements.txt .
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0
    
RUN pip install --no-cache-dir -r requirements.txt

# Copy everything from the current directory to the container
COPY . .

EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
