# Ownership Trigger Agent service
FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
# Copy project
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY . /app
EXPOSE 8001
CMD ["python", "-m", "uvicorn", "services.ownership-trigger.app.main:app", "--host", "0.0.0.0", "--port", "8001"]
