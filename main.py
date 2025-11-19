from fastmcp import FastMCP
from docling.document_converter import DocumentConverter
from pathlib import Path
from llama_cloud_services import LlamaParse
from playwright.async_api import async_playwright
import os
import tempfile
import shutil
from pypdf import PdfReader, PdfWriter
import requests
import time
from typing import Literal, Union
import pandas as pd
import json
import sys
import io

# bring in our LLAMA_CLOUD_API_KEY
from dotenv import load_dotenv
load_dotenv()


# Global cache for large responses
response_cache = {}
cache_counter = 0


# Create a basic server instance with logging disabled
mcp = FastMCP(name="good-filings")

# Create a DocumentConverter instance for docling
docling_parser = DocumentConverter()

# Create LlamaParse instance for default parsing
llama_parser = LlamaParse(
    api_key=os.environ.get("LLAMA_CLOUD_API_KEY"),
    
    # --- Output Format ---
    result_type="markdown",

    # --- OCR / Language ---
    language="en",                   # Primary language for OCR (if used)
    disable_ocr=True,                # Disable OCR to improve speed (SEC PDFs are text-based)

    # --- Layout Handling ---
    hide_headers=True,               # Remove repeating page headers (cleaner output)
    hide_footers=True,               # Remove repeating footers/page numbers
    skip_diagonal_text=True,         # Ignore diagonal watermark text if present
    do_not_unroll_columns=False,     # Keep automatic column unrolling ON for multi-column reports

    # --- Table Handling (Important for 10-K financials) ---
    merge_tables_across_pages_in_markdown=True,  # Combine multi-page financial tables
    preserve_layout_alignment_across_pages=True, # Keep column alignment across pages

    # --- Performance Tweaks ---
    num_workers=8,                   # Increase parallelism for faster parsing
    split_by_page=True,              # Process pages independently (SEC docs = many pages → improves speed)
)

# Ensure robust path resolution in any environment
PROJECT_ROOT = Path(os.path.abspath(os.path.dirname(__file__)))

def split_pdf_into_chunks(pdf_path: Path, pages_per_chunk: int = 40) -> tuple[list[tuple[int, int, Path]], Path]:
    """Split PDF into chunks and return (list of (start_page, end_page, chunk_path) tuples, temp_dir).
    
    Args:
        pdf_path: Path to the PDF file
        pages_per_chunk: Number of pages per chunk (default: 40, max: 40)
    """
    # Ensure pages_per_chunk doesn't exceed maximum
    pages_per_chunk = min(pages_per_chunk, 40)
    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)
    chunks = []
    temp_dir = Path(tempfile.mkdtemp())
    
    for start_page in range(0, total_pages, pages_per_chunk):
        end_page = min(start_page + pages_per_chunk, total_pages)
        writer = PdfWriter()
        
        for page_num in range(start_page, end_page):
            writer.add_page(reader.pages[page_num])
        
        chunk_path = temp_dir / f"chunk_{start_page}_{end_page}.pdf"
        with open(chunk_path, "wb") as chunk_file:
            writer.write(chunk_file)
        
        chunks.append((start_page, end_page, chunk_path))
    
    return chunks, temp_dir


@mcp.tool
async def read_as_markdown(
    input_file_path: str, 
    engine: str = "llama-cloud"
) -> str:
    """Read a PDF file and convert it to markdown format.
    
    Args:
        input_file_path: Path to the PDF file relative to the project root (e.g., "pdf/file.pdf")
        engine: Parsing engine to use. "llama-cloud" (default) uses LlamaParse, "docling" uses local docling converter
    """
    source = PROJECT_ROOT / input_file_path
    chunk_size = 40  # Fixed chunk size for large PDF splitting
    
    # Check if file exists
    if not source.exists():
        raise FileNotFoundError(f"File not found: {input_file_path}. Please check the file path.")
    
    # Suppress stdout/stderr to avoid JSON parsing errors in MCP
    # External libraries (docling, pypdf, llama-cloud) may print to stdout/stderr
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()
    
    try:
        # Parse based on engine
        if engine == "docling":
            # Use docling for local parsing (synchronous)
            doc = docling_parser.convert(str(source)).document
            result_text = doc.export_to_markdown()
        else:
            # Default: Use LlamaParse with async aparse method, fallback to docling on error
            try:
                # Check PDF size first
                reader = PdfReader(str(source))
                total_pages = len(reader.pages)
                
                # For large PDFs, split into chunks and process
                if total_pages > chunk_size:
                    chunks, temp_dir = split_pdf_into_chunks(source, chunk_size)
                    results = {}
                    
                    try:
                        chunk_paths = [str(chunk_path) for _, _, chunk_path in chunks]
                        
                        # Use async batch parsing - LlamaParse handles parallelism internally
                        job_results = await llama_parser.aparse(chunk_paths)
                        
                        # Extract markdown from results and store with index
                        for idx, job_result in enumerate(job_results):
                            if hasattr(job_result, 'pages'):
                                markdown = "\n\n".join([page.md for page in job_result.pages])
                            else:
                                # Fallback if structure is different
                                markdown = str(job_result)
                            results[idx] = markdown
                        
                        # Combine results in order
                        result_text = "".join([
                            results[idx] for idx in sorted(results.keys())
                        ])
                    finally:
                        # Clean up temp directory and all chunk files
                        if temp_dir.exists():
                            shutil.rmtree(temp_dir)
                else:
                    # Process entire PDF at once (for small PDFs)
                    result = await llama_parser.aparse(str(source))
                    result_text = "\n\n".join([page.md for page in result.pages])
            except Exception as e:
                # Fallback to docling if LlamaParse fails
                doc = docling_parser.convert(str(source)).document
                result_text = doc.export_to_markdown()
    finally:
        # Restore stdout/stderr
        sys.stdout = old_stdout
        sys.stderr = old_stderr
    
    # Store in cache to handle large responses
    global cache_counter, response_cache
    cache_id = f"markdown_{cache_counter}"
    response_cache[cache_id] = result_text
    cache_counter += 1
    
    # Return cache reference with metadata
    return json.dumps({
        "status": "success",
        "cache_id": cache_id,
        "total_chars": len(result_text),
        "total_kb": round(len(result_text) / 1024, 2),
        "message": f"Markdown content cached. Use 'get_markdown_segment' tool to retrieve content in chunks. Total size: {round(len(result_text) / 1024, 2)} KB"
    })



@mcp.tool
async def get_markdown_segment(cache_id: str, offset: int = 0) -> str:
    """Retrieve a segment of cached markdown content.
    
    Args:
        cache_id: The cache ID returned from read_as_markdown
        offset: Starting character position (default: 0)
    
    Returns:
        A JSON response with the requested segment and metadata (100KB chunks)
    """
    # Fixed chunk size
    length = 100000
    
    # Validate cache_id
    if cache_id not in response_cache:
        return json.dumps({
            "error": f"Cache not found: {cache_id}",
            "available_caches": list(response_cache.keys())
        })
    
    content = response_cache[cache_id]
    total_length = len(content)
    
    # Validate offset
    if offset >= total_length:
        return json.dumps({
            "error": f"Offset {offset} is beyond content length {total_length}"
        })
    
    # Extract segment
    segment = content[offset:offset + length]
    has_more = offset + length < total_length
    next_offset = offset + length if has_more else None
    
    return json.dumps({
        "status": "success",
        "cache_id": cache_id,
        "segment": segment,
        "offset": offset,
        "length": len(segment),
        "total_length": total_length,
        "has_more": has_more,
        "next_offset": next_offset,
        "progress": f"{min(offset + length, total_length)}/{total_length} characters"
    })


@mcp.tool
async def html_to_pdf(input_file_path: str, output_file_path: str) -> str:
    """Convert an HTML file to PDF using Playwright.
    
    Args:
        input_file_path: Path to the HTML file relative to the project root (e.g., "html/file.htm")
        output_file_path: Path where the PDF will be saved relative to the project root (e.g., "pdf/output.pdf")
    
    Returns:
        Success message with the output file path
    """
    source_html = PROJECT_ROOT / input_file_path
    output_pdf = PROJECT_ROOT / output_file_path
    
    # Check if HTML file exists
    if not source_html.exists():
        raise FileNotFoundError(f"HTML file not found: {input_file_path}. Please check the file path.")
    
    # Ensure output directory exists
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert HTML to PDF using Playwright Async API
    async with async_playwright() as playwright:
        chromium = playwright.chromium
        browser = await chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(f"file://{source_html}")
        await page.emulate_media(media="screen")
        await page.pdf(path=str(output_pdf))
        await browser.close()
    
    # Return success response in JSON format
    return json.dumps({
        "output_file_path": str(output_pdf)
    })

@mcp.tool
def download_sec_filing(
    cik: Union[str, int],
    year: int,
    filing_type: Literal["8-K", "10-Q", "10-K", "DEF 14A"],
    output_dir_path: str,
) -> str:
    """
    Download SEC / EDGAR Filing Document

    Args:
        cik: Company CIK (with or without leading zeros)
        year: Year to search for (2021 ~ 2025)
        filing_type: Type of filing ("8-K" | "10-Q" | "10-K" | "DEF 14A")
        output_dir_path: Output directory path under html folder (e.g., "html/amzn_2024_8_k")

    Returns:
        Local file path of the downloaded primary document on success.
        Error message string on failure.
    """
    try:
        # 1. Input validation
        if not (2021 <= int(year) <= 2025):
            return "Error: year must be between 2021 and 2025."

        # Validate output directory is under html folder
        normalized = output_dir_path.replace("\\", "/")
        if not (normalized == "html" or normalized.startswith("html/")):
            return 'Error: output_dir_path must be "html" or "html/..." format.'

        # Extract CIK number and pad to 10 digits
        try:
            cik_int = int(str(cik).lstrip("0") or "0")
        except ValueError:
            return "Error: CIK must be a numeric string or integer."

        cik_padded = f"{cik_int:010d}"

        # 2. Fetch submissions JSON from SEC
        submissions_url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
        user_agent = os.getenv("SEC_USER_AGENT", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
        headers = {
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Accept": "application/json",
        }

        try:
            resp = requests.get(submissions_url, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as e:
            return f"Error: Failed to fetch data from SEC server. {str(e)}"
        
        # Rate limiting: SEC requires delays between requests
        time.sleep(0.5)

        # 3. Convert to DataFrame and process with pandas
        recent = data["filings"]["recent"]
        
        # Create DataFrame from all keys and values in recent
        df = pd.DataFrame(recent)

        # Use reportDate if available, otherwise use filingDate
        df['date'] = df['reportDate'].fillna(df['filingDate'])
        
        # Convert date strings to datetime
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        
        # Filter by filing type
        df_filtered = df[df['form'] == filing_type].copy()
        
        if df_filtered.empty:
            return f"Error: No filing found for CIK={cik_int}, year={int(year)}, filing_type={filing_type}."
        
        # Filter by year
        df_filtered['year'] = df_filtered['date'].dt.year
        df_filtered = df_filtered[df_filtered['year'] == int(year)].copy()
        
        if df_filtered.empty:
            return f"Error: No filing found for CIK={cik_int}, year={int(year)}, filing_type={filing_type}."
        
        # Select most recent filing (sorted by date, ascending=False)
        filing = df_filtered.sort_values('date', ascending=False).iloc[0]
        
        accession_raw = filing['accessionNumber']
        primary_doc = filing['primaryDocument']
        accession_clean = accession_raw.replace("-", "")

        # 4. Construct EDGAR Archives URL
        archives_url = (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{cik_int}/{accession_clean}/{primary_doc}"
        )

        # 5. Download and save file
        os.makedirs(output_dir_path, exist_ok=True)
        local_path = os.path.join(output_dir_path, primary_doc)

        # Add delay before downloading to avoid rate limiting
        time.sleep(0.5)
        
        try:
            doc_resp = requests.get(archives_url, headers=headers, timeout=30)
            doc_resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            return f"Error: Failed to download file. {str(e)}"

        with open(local_path, "wb") as f:
            f.write(doc_resp.content)

        # Return success response in JSON format
        return json.dumps({
            "primaryDocument": local_path,
        })
    
    except Exception as e:
        return f"Error: Unexpected error occurred. {str(e)}"


if __name__ == "__main__":
    # This runs the server, defaulting to STDIO transport
    mcp.run()

    # To use a different transport, e.g., HTTP:
    # mcp.run(transport="http", host="127.0.0.1", port=9000)