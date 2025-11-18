# good-fillings

An MCP (Model Context Protocol) server for processing SEC filings (10-K, 10-Q, 8-K, DEF 14A). This server provides tools to download SEC documents, convert them to markdown, and convert HTML to PDF.

## Features

- **Download SEC Filings**: Download various SEC filing documents (10-K, 10-Q, 8-K, DEF 14A)
- **PDF to Markdown**: Convert PDF documents to markdown format using LlamaParse or Docling
- **HTML to PDF**: Convert HTML files to PDF using Playwright

## Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (Python package manager)
- [Claude Desktop](https://claude.ai/download) (to use this MCP)
- API Keys:
  - `LLAMA_CLOUD_API_KEY` (from [LlamaIndex](https://cloud.llamaindex.ai/))

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/doongeon/good-filings.git
cd good-filings
```

## Claude Desktop Setup

### 1. Find Claude Desktop Config Location

**macOS:**

```bash
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Windows:**

```
%APPDATA%\Claude\claude_desktop_config.json
```

**Linux:**

```
~/.config/Claude/claude_desktop_config.json
```

### 2. Update Claude Desktop Configuration

First, get your API key from [LlamaIndex Cloud](https://cloud.llamaindex.ai/).

#### Option A: Using Local Installation (run.sh)

First, install dependencies using uv:

```bash
uv sync
```

Then, add this MCP server to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "good-fillings": {
      "command": "/absolute/path/to/good-filings/run.sh",
      "env": {
        "LLAMA_CLOUD_API_KEY": "your-actual-api-key-here"
      }
    }
  }
}
```

**Important:**

- Replace `/absolute/path/to/good-filings/run.sh` with the actual absolute path to your cloned repository's `run.sh` file
- Replace `your-actual-api-key-here` with your actual LlamaIndex Cloud API key

#### Option B: Using Docker

1. Build the Docker image:

```bash
docker build -f Dockerfile -t gf-docker .
```

2. Add this configuration to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "good-filings": {
      "transport": "stdio",
      "command": "docker",
      "args": ["run", "-i", "--rm", "gf-docker"],
      "env": {
        "LLAMA_CLOUD_API_KEY": "your-actual-api-key-here"
      }
    }
  }
}
```

**Important:**

- Replace `your-actual-api-key-here` with your actual LlamaIndex Cloud API key
- Make sure the Docker image `gf-docker` is built and available locally

### 3. Restart Claude Desktop

Close and reopen Claude Desktop for the configuration to take effect.

## Usage

Once configured, Claude will automatically use the available tools based on your requests. Simply ask in natural language!

### Examples

Ask Claude naturally:

```
"Can I have a summary of the newest Amazon (CIK: 1018724) 8-K filing?"
"summary of the newest Amazon (CIK: 1018724) 10-Q filing"
```

**Note:** If Claude doesn't use the MCP tools, add `use mcp` at the end of your question:

```
"Can I have a summary of the newest Amazon (CIK: 1018724) 8-K filing? use mcp"
```

Claude will automatically:

1. Download the requested SEC filing
2. Convert it to markdown format
3. Provide a summary or return the content
