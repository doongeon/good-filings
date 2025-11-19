# good-filings

An MCP (Model Context Protocol) server for processing SEC filings (10-K, 10-Q, 8-K, DEF 14A). This server provides tools to download SEC documents, convert them to markdown, and convert HTML to PDF. It is fully compatible with Claude Desktop and can be used as a local MCP server.

## Features

- **Download SEC Filings**: Download various SEC filing documents (10-K, 10-Q, 8-K, DEF 14A)
- **PDF to Markdown**: Convert PDF documents to markdown format using LlamaParse (default) or Docling
  - Automatically handles large files by splitting into chunks
  - Falls back to Docling if LlamaParse fails
  - Large responses (>100KB) are cached and retrieved in 100KB segments
- **HTML to PDF**: Convert HTML files to PDF using Playwright

## Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (Python package manager)
- [Claude Desktop](https://claude.ai/download) (to use this MCP)
- Make sure `uv` is installed and available in your system `PATH`. Claude Desktop runs MCP servers in an isolated environment and relies on `uv` to manage dependencies.
- API Keys (optional):
  - `LLAMA_CLOUD_API_KEY` (from [LlamaIndex](https://cloud.llamaindex.ai/)) - Required only if using `llama-cloud` engine. Default is `llama-cloud`, but can use `docling` without API key.

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

First, get your API key from [LlamaIndex Cloud](https://developers.llamaindex.ai/typescript/cloud/general/api_key/).

#### Option A: Using Local Installation

First, install dependencies using uv:

```bash
uv sync
```

Then, add this MCP server to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "good-filings": {
      "command": "/absolute/path/to/good-filings/run.sh",
      "env": {
        "LLAMA_CLOUD_API_KEY": "your-actual-api-key-here"
      }
    }
  }
}
```

> **Warning:** `uv` must be installed and available in your system `PATH`. Claude Desktop runs MCP servers within its own isolated environment and relies on `uv` to manage dependencies, so ensure that `uv` is accessible from the command line before proceeding.

**Important:**

- Replace `/absolute/path/to/good-filings/run.sh` with the actual absolute path to your cloned repository's `run.sh` file
- Replace `your-actual-api-key-here` with your actual LlamaIndex Cloud API key

If you don’t have a Llama Cloud API key and only plan to use the Docling engine, you can omit the `env` block entirely:

```json
{
  "mcpServers": {
    "good-filings": {
      "command": "/absolute/path/to/good-filings/run.sh"
    }
  }
}
```

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

Without a Llama Cloud API key you can still run the Docker image (Docling-only) by removing the `env` section:

```json
{
  "mcpServers": {
    "good-filings": {
      "transport": "stdio",
      "command": "docker",
      "args": ["run", "-i", "--rm", "gf-docker"]
    }
  }
}
```

### 3. Restart Claude Desktop

Close and reopen Claude Desktop for the configuration to take effect.

## Usage

Once configured, Claude will automatically use the available tools based on your requests. Simply ask in natural language!

### Examples

Ask Claude naturally:

```
"Can I have a summary of the latest Amazon (CIK: 1018724) 8-K filing?"
"summary of the latest Amazon (CIK: 1018724) 10-Q filing"
"show me a markdown of the latest Amazon (cik: 1018724) 10-k filing"
```

**Note:** If Claude doesn't use the MCP tools, add `use mcp` at the end of your question:

```
"Can I have a summary of the latest Amazon (CIK: 1018724) 8-K filing? use mcp"
```

Claude will automatically:

1. Download the requested SEC filing
2. Convert it to markdown format (default: llama-cloud, can use docling by specifying `engine="docling"`)
3. For large files (>100KB), content is cached and retrieved in 100KB segments
4. Provide a summary or return the content

**Note about large files:** When processing very large PDFs, the markdown content is cached and Claude will automatically retrieve it in chunks using the `get_markdown_segment` tool. This prevents MCP response size limits.

## Available MCP Tools

### `read_as_markdown`

- **Purpose**: Convert a PDF (located within the repo) into markdown text.
- **Parameters**:
  - `input_file_path`: Relative path to the PDF (e.g., `pdf/sample.pdf`)
  - `engine`: `"llama-cloud"` (default, requires `LLAMA_CLOUD_API_KEY`) or `"docling"` (local, no API key required)
  - `direct_response`: `false` by default. When set to `true`, returns the entire markdown text directly (intended for testing only, since responses can exceed MCP limits)
- **Behavior**:
  - Uses LlamaParse with automatic fallback to Docling
  - Splits large PDFs into 40-page chunks before sending to LlamaParse
  - Suppresses stdout/stderr while parsing to keep MCP JSON clean
  - If `direct_response=false` (default), caches the markdown and returns metadata (cache ID, size, etc.)

### `get_markdown_segment`

- **Purpose**: Retrieve portions of cached markdown content emitted by `read_as_markdown`
- **Parameters**:
  - `cache_id`: ID returned by `read_as_markdown`
  - `offset`: starting character index (default `0`)
- **Behavior**:
  - Returns 100,000-character segments to stay within MCP response limits
  - Includes metadata about total length, next offset, and whether more content remains

### `html_to_pdf`

- **Purpose**: Convert HTML files (within the repo) into PDFs using Playwright Chromium
- **Parameters**:
  - `input_file_path`: Relative path to HTML file (e.g., `html/report.html`)
  - `output_file_path`: Relative destination path for the PDF (e.g., `pdf/report.pdf`)
- **Behavior**:
  - Uses Playwright’s headless Chromium to render the HTML and save as PDF
  - Automatically ensures the output directory exists

### `download_sec_filing`

- **Purpose**: Fetch SEC filings (10-K/10-Q/8-K/DEF 14A) for a given CIK and year
- **Parameters**:
  - `cik`: Company CIK (string or int)
  - `year`: Year of filing (2021–2025)
  - `filing_type`: `"8-K"`, `"10-Q"`, `"10-K"`, or `"DEF 14A"`
  - `output_dir_path`: Directory (under `html/`) where the filing will be saved
- **Behavior**:
  - Uses SEC EDGAR endpoints with rate limiting
  - Saves primary documents locally for subsequent conversion
