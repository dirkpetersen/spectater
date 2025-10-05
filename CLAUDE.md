# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SpecTater is a Flask web application that evaluates whether submission documents meet requirements specified in policy documents. It uses AWS Bedrock (Claude or Amazon Nova models) to perform intelligent document comparison, with special emphasis on numerical values and tabular data.

## Core Architecture

### Document Processing Pipeline
1. **Upload** → Web form accepts multiple PDF/TXT/HTML/MD files for both policy and submission documents
2. **Text Extraction** → `extract_text_from_file()` converts documents to markdown using pymupdf4llm with table-aware processing
3. **LLM Evaluation** → `evaluate_requirements()` sends documents to AWS Bedrock for analysis using a strict pass/fail prompt
4. **Result Display** → Color-coded results (GREEN/YELLOW/ORANGE/RED) with explanations

### Key Components

**app.py** - Main Flask application
- `get_bedrock_client()` - Initializes AWS Bedrock client with retry configuration
- `extract_text_from_file()` - Handles PDF→markdown conversion with table preservation using `pymupdf4llm`
- `_html_table_to_md()` - Converts HTML tables to markdown with proper alignment
- `evaluate_requirements()` - Sends policy+submission to LLM and parses color-coded response
- User-specific policy caching via cookies (`policy_cache/policy_{user_id}.txt`)

**pdf2md.py** - CLI tool for PDF→markdown conversion
- Reuses `extract_text_from_file()` from app.py
- MockFile class simulates Flask file uploads for CLI use

**testcheck.py** - CLI tool for evaluation without web interface
- Command: `./testcheck.py --spec policy.pdf --submit document.pdf`
- Uses cached policy if --spec omitted
- Monkey-patches `get_user_id()` to return 'cli_user'

**analysis-prompt.txt** - LLM prompt template
- Enforces strict pass/fail evaluation
- Emphasizes numerical requirements must meet or exceed minimums
- Response format: Start with GREEN or RED, followed by explanation

### AWS Bedrock Integration
- Models: Configured via MODEL_ID env var (default: amazon.nova-lite-v1:0)
- Authentication: Uses boto3 session with local AWS credentials
- Retry: Configurable max_attempts (default: 10 retries)
- Response parsing: Extracts status from Claude 3 message format with content array

### Policy Caching System
- Per-user cache: `policy_cache/policy_{user_id}.txt`
- User tracking: Cookie-based (`spectater_id` cookie, 30-day expiry)
- Allows reusing policy across multiple submissions without re-upload

## Development Commands

### Run Development Server
```bash
python app.py
# Runs on http://0.0.0.0:5000 (or HTTPS if SSL_CERT/SSL_KEY configured)
# Debug mode controlled by FLASK_DEBUG env var
```

### CLI Document Conversion
```bash
# Convert PDF to markdown
./pdf2md.py input.pdf output.md
./pdf2md.py input.pdf  # Auto-generates output filename
```

### CLI Document Evaluation
```bash
# Evaluate submission against policy
./testcheck.py --spec policy.pdf --submit document.pdf

# Use cached policy from previous run
./testcheck.py --submit document.pdf
```

### Dependencies
```bash
pip install -r requirements.txt
# Key packages: flask, boto3, pymupdf4llm, beautifulsoup4
```

## Configuration

Environment variables are loaded from `.env` file (see `.env.default` for template):

**AWS Configuration**
- `MODEL_ID` - Bedrock model (anthropic.claude-* or amazon.nova-*)
- `AWS_REGION` - AWS region (default: us-west-2)
- `MAX_RETRIES` - Bedrock API retry attempts

**Application Settings**
- `FLASK_DEBUG` - Enable debug mode
- `FLASK_PORT` - Server port (default: 5000)
- `MAX_CONTENT_LENGTH` - Max upload size in bytes (default: 128MB)

**LLM Parameters**
- `MAX_TOKENS` - Response token limit
- `TEMPERATURE` - Model temperature
- `MAX_CHARS_PER_DOC` - Character limit per document

**Caching**
- `CACHE_DIR` - Policy cache directory (default: policy_cache)
- `COOKIE_NAME` - User tracking cookie name
- `COOKIE_MAX_AGE` - Cookie expiry in seconds (default: 30 days)

## Important Implementation Details

### Table Processing
- Uses pymupdf4llm with `table_strategy="lines_strict"` for accurate table detection
- HTML tables converted to markdown pipes with alignment preservation
- Critical for numerical requirement comparison

### Document Text Extraction
- Supports PDF, TXT, HTML, MD formats
- PDFs processed with pymupdf4llm to maintain structure
- Text files read directly
- HTML tables converted to markdown for consistent LLM parsing

### Error Handling
- File validation via `validate_file_type()` before processing
- AWS Bedrock errors logged with detailed context
- Response parsing validates Claude 3 message structure (content array with text blocks)

### Response Format
The LLM returns one of four statuses:
- **GREEN** - All requirements fully met
- **YELLOW** - Numerical requirements met but other requirements ambiguous
- **ORANGE** - Both numerical and other requirements ambiguous
- **RED** - One or more requirements not met

Status word is extracted and removed from explanation text before display.

## Testing

Test documents located in `test/` directory:
- `test/Valid-COI/` - Documents that should pass evaluation
- `test/Invalid-COI/` - Documents that should fail evaluation

Use `testcheck.py` with these samples to verify behavior.
