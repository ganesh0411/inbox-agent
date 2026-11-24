# Stage 1: build the React app. Render's Python image has no Node.
FROM node:20-slim AS web
WORKDIR /web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Stage 2: the app itself
FROM python:3.13-slim
WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=web /web/dist ./web/dist

# Seed the inbox and build the index at image build time. This also downloads
# the embedding model into the image, so the first request after a cold start
# doesn't pay for a 67MB download.
RUN python demo/seed_inbox.py \
 && python index_build.py --src data/demo_messages.jsonl --db data/demo_index.db

ENV DEMO_MODE=true \
    INDEX_DB=data/demo_index.db \
    PYTHONUNBUFFERED=1

# The calendar is seeded at start, not at build, so its dates stay relative
# to today rather than freezing at whenever the image was built.
CMD python demo/seed_calendar.py && \
    uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000}
