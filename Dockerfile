FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY tse tse
COPY config config
RUN useradd --create-home app
USER app
EXPOSE 8000
ENV TSE_SERVE=1
HEALTHCHECK --interval=5s --retries=10 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
# Point TSE_DB at Postgres in production; the default is SQLite in memory.
CMD ["uvicorn", "tse.product.api:app", "--host", "0.0.0.0", "--port", "8000"]
