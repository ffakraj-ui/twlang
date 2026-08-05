# Dockerfile for a TW Framework project.
# Place this file in your project root (next to tw.config) and build with:
#   docker build -t my-tw-site .
#   docker run -p 8000:8000 my-tw-site

FROM python:3.12-slim AS build

WORKDIR /app

RUN pip install --no-cache-dir tw-framework

COPY . .

RUN tw build

# ---- Runtime stage ----
FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir tw-framework

COPY --from=build /app /app

ENV TW_HOST=0.0.0.0
ENV TW_PORT=8000

EXPOSE 8000

CMD ["tw", "serve", "--no-build"]
