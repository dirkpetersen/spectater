# SpecTater

Check if a document meets the requirements specified in another document using AI-powered analysis.

## Overview

SpecTater is a Flask web application that uses AWS Bedrock (Claude or Amazon Nova models) to automatically evaluate whether submission documents (like Certificates of Insurance) meet requirements specified in policy documents. The application returns detailed, structured JSON results with pass/fail analysis for each requirement.

## Key Features

- **Intelligent Document Analysis** - Uses LLM to compare submissions against policy requirements
- **Multiple Format Support** - Accepts PDF, TXT, and Markdown files
- **AWS Textract Integration** - Automatically processes PDFs with tables using OCR
- **Structured JSON Output** - Returns detailed pass/fail for each requirement
- **Session-Based Caching** - Reuses policy documents across submissions
- **IP Subnet Restriction** - Optional access control by IP range
- **CLI Testing Tools** - Fast iteration with markdown files, wildcard support
- **Customizable UI** - Configure title, introduction, and static requirements

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/dirkpetersen/spectater.git
cd spectater

# Install dependencies
pip install -r requirements.txt

# Configure environment (copy and edit)
cp .env.default .env
# Edit .env to set your AWS credentials and MODEL_ID
```

### Configuration

Key settings in `.env`:

```bash
# AWS Bedrock Model (use inference profile for Sonnet 4)
MODEL_ID='us.anthropic.claude-sonnet-4-5-20250929-v1:0'

# Application Settings
FLASK_DEBUG=True
FLASK_PORT=5000

# Optional: IP Subnet Restriction
# SUBNET_ONLY='192.168.0.0/16'  # Allow only this subnet
# SUBNET_ONLY='127.0.0.1/32'    # Localhost only (default)

# Optional: UI Customization
# TITLE='My Custom Title'
# INTRODUCTION='intro.txt'       # Show intro text from file
# REQUIREMENTS='requirements.md'  # Use static requirements (hides upload)
```

### Run the Application

```bash
python app.py
# Access at http://localhost:5000
```

## Usage

### Web Interface

1. **Upload Policy Document** (PDF, TXT, or MD)
   - Contains the requirements to check against
   - Cached per session for reuse
   - Or use `REQUIREMENTS=file.md` in .env for static requirements

2. **Upload Submission Document** (PDF or MD)
   - The document to be evaluated
   - PDFs with tables automatically use Textract OCR
   - Auto-submits and shows progress messages

3. **View Results**
   - **Status Box**: GREEN (pass) or RED (fail)
   - **Detailed Table**: Pass/fail for each requirement with color coding
   - **Raw JSON**: Complete structured output with model ID

### CLI Testing Tool

Fast iteration without web browser:

```bash
# Basic usage
./testeval.py --spec requirements.md --submit document.md

# With debug output (shows JSON parsing, model info)
./testeval.py --spec requirements.md --submit document.md --debug

# Batch testing with wildcards (runs separate evaluation for each)
./testeval.py --spec requirements.md --submit 'cache/*/submission_*.md' --debug
```

### PDF Conversion Tool

```bash
# Convert PDF to markdown
./pdf2md.py certificate.pdf certificate.md

# Auto-generate output filename
./pdf2md.py certificate.pdf
```

## Response Format

The LLM returns structured JSON:

```json
{
  "summary": {
    "statement": "Overall compliance assessment",
    "totalChecks": 10,
    "passed": 8,
    "failed": 2
  },
  "requirements": [
    {
      "requirement": "General Liability Limit",
      "policyRequirement": "$2,000,000 per occurrence",
      "submissionValue": "$1,000,000 per occurrence",
      "pass": false,
      "notes": "Does not meet minimum requirement"
    }
  ]
}
```

**Status Determination:**
- Automatically checks all `pass` fields in requirements array
- **RED** if any requirement has `pass: false`
- **GREEN** if all requirements have `pass: true`
- Validates summary counts match actual requirements (shows warning if inconsistent)

## Advanced Features

### AWS Textract for Complex PDFs

When a PDF contains tables, the app automatically:
1. Creates temporary S3 bucket (if needed)
2. Uploads PDF to S3
3. Runs Textract OCR analysis
4. Converts results to markdown
5. Cleans up S3 objects
6. Deletes bucket on app shutdown

### Session & Caching

- **Session-based**: Flask sessions (not cookies) track users
- **Cache Structure**: `cache/{session_id}/policy.md` and `cache/{session_id}/submission_{hash}.md`
- **Debug Mode**: Submission documents cached only when `FLASK_DEBUG=True`
- **Hash-based**: Submission cache uses filename hash for consistent lookups

### Dynamic Token Allocation

- Automatically calculates max_tokens as **2/3 of input bytes**
- Minimum 5000 tokens to prevent JSON truncation
- Uses `MAX_TOKENS` from .env as floor if configured
- Extended 1M token context for Claude Sonnet 4 (when tokens > 200,000)

### IP Subnet Restriction

Restrict access by IP address:

```bash
SUBNET_ONLY='10.10.0.0/16'     # Allow 10.10.x.x
SUBNET_ONLY='192.168.1.0/24'   # Allow 192.168.1.x
SUBNET_ONLY='127.0.0.1/32'     # Localhost only (default)
SUBNET_ONLY='0.0.0.0/0'        # Allow all (no restriction)
```

Unauthorized users see: "You are not authorized to access this application from your location. You may need to connect via VPN with split tunneling DISABLED."

### UI Customization

Create a customized experience:

```bash
# Custom title
TITLE='OSU Insurance Compliance Checker'

# Show introduction text
INTRODUCTION='welcome.txt'

# Use static requirements (hides policy upload field)
REQUIREMENTS='osu-requirements.md'
```

## Architecture Details

### File Processing
- **Policy Files**: PDF, TXT, MD → Always cached
- **Submission Files**: PDF (with Textract for tables), MD → Cached in debug mode
- **Character Limiting**: Applied after markdown conversion (configurable)

### LLM Configuration
- **Temperature**: Hardcoded to 0 (deterministic output)
- **Cache Control**: Disabled (`cache_control: {"type": "ephemeral"}`)
- **Prompt Template**: `analysis-prompt.md` (uses string replacement, not .format())

### Progress Feedback
When processing documents, users see rotating status messages:
- Uploading documents...
- Reading PDF files...
- Detecting tables and complex elements...
- Processing tables with OCR if needed...
- Analyzing submission against requirements...
- (14 messages total, changing every 3 seconds)

## Troubleshooting

### JSON Parse Errors
If you see "Expecting ',' delimiter" errors:
- Increase MAX_TOKENS in .env (or remove to use dynamic calculation)
- Try a model with higher output capacity (Sonnet vs Haiku)
- Check debug output to see where JSON truncates

### Model Access Issues
Claude Sonnet 4 requires inference profile ARN:
```bash
# Use this (with inference profile)
MODEL_ID='us.anthropic.claude-sonnet-4-5-20250929-v1:0'

# Not this (direct model ID won't work)
MODEL_ID='anthropic.claude-sonnet-4-5-20250929-v1:0'
```

### Inconsistent Results Warning
If summary counts don't match requirements:
- Review `analysis-prompt.md` for clarity
- Check if policy document has ambiguous requirements
- Enable debug mode to see actual vs summary counts

## Development

### Debug Mode Benefits
When `FLASK_DEBUG=True`:
- Submission documents cached for faster re-testing
- Console shows LLM response preview
- JSON parsing details printed
- Summary count validation logged

### Testing Strategy
1. Use `testeval.py` with markdown files for rapid prompt iteration
2. Use wildcard patterns to batch-test multiple submissions
3. Enable `--debug` flag to see complete JSON parsing flow
4. Check cache files in `cache/{session_id}/` to verify extraction

## License

MIT License - see LICENSE file

## Requirements

- Python 3.12+
- AWS account with Bedrock access
- AWS credentials configured (via ~/.aws/credentials or environment variables)
- For Textract: S3 and Textract permissions

## AWS Permissions

The application requires the following AWS IAM permissions:

### Minimum Permissions (Basic Operation)

For basic PDF analysis without Textract:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel"
      ],
      "Resource": [
        "arn:aws:bedrock:*::foundation-model/anthropic.claude-*",
        "arn:aws:bedrock:*::foundation-model/amazon.nova-*"
      ]
    }
  ]
}
```

### Full Permissions (With Textract Support)

For complete functionality including table extraction from PDFs:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel"
      ],
      "Resource": [
        "arn:aws:bedrock:*::foundation-model/anthropic.claude-*",
        "arn:aws:bedrock:*::foundation-model/amazon.nova-*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:DeleteBucket",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::spectater-textract-*",
        "arn:aws:s3:::spectater-textract-*/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "textract:AnalyzeDocument",
        "textract:GetDocumentAnalysis"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "sts:GetCallerIdentity"
      ],
      "Resource": "*"
    }
  ]
}
```

**Note:** The S3 bucket is created automatically with the naming pattern `{APP_NAME}-textract-{account_id}-{region}` and is cleaned up when the application shuts down.
