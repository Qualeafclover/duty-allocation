FROM python:3.12-slim
WORKDIR /code
RUN pip install uv
COPY pyproject.toml uv.lock ./
RUN uv sync --locked
ENV PATH="/code/.venv/bin:$PATH"
COPY backend/ backend/
COPY frontend/ frontend/
WORKDIR /code/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
