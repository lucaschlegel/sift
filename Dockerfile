FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV JOBRADAR_DATA_DIR=/app/data
EXPOSE 8000
# Der Dienst liest nur data/. Rechnen: docker run ... python -m jobradar run (braucht ANTHROPIC_API_KEY)
CMD ["uvicorn", "jobradar.api:app", "--host", "0.0.0.0", "--port", "8000"]
