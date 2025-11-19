# Dockerfile for good-filings MCP server
# Reference: https://pradappandiyan.medium.com/how-to-run-python-playwright-tests-using-docker-locally-4417392b20e2
# Reference: https://medium.com/@smrati.katiyar/building-mcp-server-client-using-fastmcp2-and-converting-them-into-docker-images-541c2320bcca

FROM ghcr.io/astral-sh/uv:python3.12-trixie-slim

# Copy the project into the image
COPY . /app

# Sync the project into a new environment
WORKDIR /app
RUN uv sync --locked

# Install Playwright browsers and system dependencies
RUN uv run playwright install --with-deps

# Set the default command
CMD ["uv", "run", "main.py"]