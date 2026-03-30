FROM python:3.12-slim AS base

LABEL maintainer="aarjay"
LABEL description="OpenArangoDB MCP Server — Enterprise-equivalent features for ArangoDB Community Edition"

WORKDIR /app

# Install only production dependencies first for caching
COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir ".[mcp]"

ENV ARANGODB_HOST=http://host.docker.internal:8529
ENV ARANGODB_DATABASE=argondb
ENV ARANGODB_USERNAME=root
ENV ARANGODB_PASSWORD=
ENV ARANGODB_AUDIT=true
ENV ARANGODB_CDC=true
ENV ARANGODB_RETRIEVAL=false
ENV ARANGODB_TEMPORAL=false
ENV ARANGODB_GRAPH=false

ENTRYPOINT ["openarangodb", "serve"]
