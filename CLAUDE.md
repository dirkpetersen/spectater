# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SpecTater is a Flask web application that evaluates whether submission documents meet requirements specified in policy documents. It uses AWS Bedrock (Claude or Amazon Nova models) to perform intelligent document comparison and returns structured JSON results with detailed pass/fail analysis.

## Core Architecture

### Document Processing Pipeline
1. **Upload** → Web form accepts PDF/TXT/MD files for policy (or static file) and PDF/MD for submissions
2. **Text Extraction** → `extract_text_from_file()` converts documents to markdown
   - PDFs: Uses pymupdf4llm for simple PDFs or AWS Textract for PDFs with tables
   - TXT/MD: Read directly without conversion
3. **LLM Evaluation** → `evaluate_requirements()` sends documents to AWS Bedrock for JSON analysis
4. **Result Display** → Bootstrap table showing pass/fail for each requirement with color coding

### Key Components

**app.py** - Main Flask application
- `get_bedrock_client()` - Initializes AWS Bedrock client with retry configuration
- `extract_text_from_file()` - Handles document conversion:
  - PDFs with tables → AWS Textract OCR processing
  - Simple PDFs → pymupdf4llm conversion
  - TXT/MD → Direct reading
- `analyze_pdf_with_textract()` - Uploads PDF to S3, runs Textract, retrieves results
- `convert_textract_to_markdown()` - Converts Textract output to markdown
- `evaluate_requirements()` - Sends to LLM, extracts JSON, determines RED/GREEN status
- Session-based caching in `cache/{session_id}/` directory

**testeval.py** - CLI tool for fast testing with markdown files
- Bypasses PDF processing for rapid iteration
- Supports wildcards: `--submit 'cache/*/submission_*.md'`
- Runs separate evaluation for each matched submission file
- Debug mode shows full JSON parsing details
- Command: `./testeval.py --spec policy.md --submit document.md [--debug]`

**pdf2md.py** - CLI tool for PDF→markdown conversion
- Reuses `extract_text_from_file()` from app.py
- MockFile class simulates Flask file uploads

**analysis-prompt.md** - LLM prompt template
- Instructs LLM to output structured JSON with pass/fail for each requirement
- Format: `{"summary": {...}, "requirements": [...]}`
- Uses placeholder replacement instead of .format() to avoid conflicts with JSON braces

### AWS Integration

**Bedrock**
- Models: Configured via MODEL_ID (use inference profiles like `us.anthropic.claude-sonnet-4-5-20250929-v1:0`)
- Authentication: boto3 session with local AWS credentials
- Retry: Configurable max_attempts (default: 10)
- Temperature: Hardcoded to 0 for deterministic results
- Max Tokens: Dynamic calculation (2/3 of input bytes, minimum 5000)
- Extended context: Automatically adds 1M token context for Claude Sonnet 4 when MAX_TOKENS > 200000
- Cache control: Disables LLM caching with `cache_control: {"type": "ephemeral"}`

**Textract & S3**
- Temporary bucket created on-demand: `{APP_NAME}-textract-{account_id}-{region}`
- Bucket lifecycle: Created when first needed, deleted on app shutdown
- PDFs with tables automatically trigger Textract OCR processing
- Objects deleted after processing, bucket cleaned up via atexit handler

### Session & Caching System
- Flask sessions (not cookies) for user tracking
- Per-session cache: `cache/{session_id}/policy.md` and `cache/{session_id}/submission_{hash}.md`
- Policy documents: Always cached
- Submission documents: Only cached in debug mode (filename hash-based)
- Character limiting: MAX_CHARS_PER_DOC truncates documents after conversion (0 = unlimited)

### JSON Response Processing
- LLM returns structured JSON with requirements array
- Status determination: Iterates through requirements checking `pass` field
- RED if any requirement has `pass: false`, otherwise GREEN
- Consistency check: Verifies summary counts match actual requirement counts
- Warning displayed if inconsistent (suggests reviewing prompt or policy)
- Brace-counting extraction: Captures complete JSON even if nested

## Development Commands

### Run Development Server
```bash
python app.py
# Runs on http://0.0.0.0:5000 (or HTTPS if SSL_CERT/SSL_KEY configured)
# Debug mode controlled by FLASK_DEBUG env var
```

### CLI Testing (Fast Iteration)
```bash
# Test with markdown files (no PDF processing)
./testeval.py --spec policy.md --submit document.md

# With debug output (shows JSON parsing, model info)
./testeval.py --spec policy.md --submit document.md --debug

# Test multiple submissions with wildcards
./testeval.py --spec policy.md --submit 'cache/*/submission_*.md' --debug
```

### CLI Document Conversion
```bash
# Convert PDF to markdown
./pdf2md.py input.pdf output.md
./pdf2md.py input.pdf  # Auto-generates output filename
```

### Dependencies
```bash
pip install -r requirements.txt
# Key packages: flask, boto3, pymupdf4llm, amazon-textract-response-parser
```

## Configuration

Environment variables loaded from `.env` or `.env.default`:

**AWS Configuration**
- `MODEL_ID` - Bedrock model (use inference profile ARN for Sonnet 4)
- `AWS_REGION` - AWS region (default: us-west-2)
- `MAX_RETRIES` - Bedrock API retry attempts (default: 10)

**Application Settings**
- `APP_NAME` - Application name (used for S3 bucket naming)
- `FLASK_DEBUG` - Enable debug mode (enables submission caching)
- `FLASK_PORT` - Server port (default: 5000)
- `MAX_CONTENT_LENGTH` - Max upload size in bytes (default: 128MB)
- `SUBNET_ONLY` - IP subnet restriction (e.g., '192.168.0.0/16', default: '127.0.0.1/32')

**UI Customization**
- `TITLE` - Custom page title (default: "Policy / Requirements Evaluator")
- `INTRODUCTION` - Path to introduction text file (displayed in info box)
- `REQUIREMENTS` - Path to static requirements file (hides policy upload)

**LLM Parameters**
- `MAX_TOKENS` - Minimum token limit (actual is dynamic: 2/3 of input bytes)
- `MAX_CHARS_PER_DOC` - Character limit per document (0 = unlimited)

**Caching**
- `CACHE_DIR` - Cache directory (default: cache)

## Important Implementation Details

### File Type Validation
- Policy documents: PDF, TXT, MD allowed
- Submission documents: PDF, MD allowed
- Backend validation enforces these restrictions

### Table Processing with Textract
- PDFs with tables automatically use AWS Textract OCR
- Creates temporary S3 bucket for Textract processing
- User sees progress messages updating every 3 seconds
- Textract results cached in debug mode

### Dynamic Token Allocation
- Calculated as 2/3 of input bytes (not 1/3)
- Minimum 5000 tokens to ensure complete JSON
- Uses configured MAX_TOKENS as floor if set
- Prevents JSON truncation mid-response

### Response Format (JSON)
```json
{
  "summary": {
    "statement": "Brief description",
    "totalChecks": 10,
    "passed": 8,
    "failed": 2
  },
  "requirements": [
    {
      "requirement": "Item name",
      "policyRequirement": "Expected value",
      "submissionValue": "Actual value",
      "pass": true/false,
      "notes": "Explanation if failed"
    }
  ]
}
```

### Security
- IP subnet restriction via SUBNET_ONLY
- Access denied page for unauthorized IPs
- Error message suggests VPN with split tunneling disabled
- Does not reveal allowed subnet range

### Session Management
- Flask sessions (permanent, 1 hour lifetime)
- Session-specific cache directories
- No cookie-based tracking (removed in favor of Flask sessions)

## Testing

Use `testeval.py` for rapid testing with markdown files:
- Bypasses PDF/Textract processing
- Supports wildcard patterns for batch testing
- Debug mode shows complete JSON parsing flow
- Each matched submission file evaluated separately

Test documents in `cache/template/` for development.
