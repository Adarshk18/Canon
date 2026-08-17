FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir ".[server]"
ENV CANON_CLOUD_HOST=0.0.0.0
EXPOSE 8787
CMD ["python", "-m", "canon.server"]
