FROM python:3.12-slim

# Hugging Face Spaces runs the container as a non-root user with uid 1000.
# Files written by root are unreadable to it, so create that user up front.
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

WORKDIR /app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY --chown=user . .

# Spaces routes public traffic to port 7860.
EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
