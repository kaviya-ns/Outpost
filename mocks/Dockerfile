FROM python:3.11-slim
WORKDIR /mocks
RUN pip install --no-cache-dir fastapi uvicorn
COPY mock_platforms.py .
CMD ["uvicorn", "mock_platforms:app", "--host", "0.0.0.0", "--port", "8080"]
