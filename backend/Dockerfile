FROM python:3.12-slim

# Run as a non-root user. Cloud Run does not require it, but a container that
# never needs root should not have it.
RUN useradd -m -u 1000 app
USER app
ENV PATH="/home/app/.local/bin:$PATH"

WORKDIR /app

COPY --chown=app requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY --chown=app . .

# Cloud Run tells the container which port to listen on through $PORT and will
# not route traffic to anything else. The default is only for running locally.
ENV PORT=8080
CMD exec uvicorn app:app --host 0.0.0.0 --port ${PORT}
