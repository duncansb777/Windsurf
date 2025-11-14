# Health Demo UI service
FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
# Copy project
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY . /app
# Configure target Ownership service via env
ENV OWNERSHIP_URL=http://ownership-trigger:8001
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "services.demo-ui.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
