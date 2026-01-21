#! /usr/bin/env python3

# Suppress multiprocessing resource tracker warnings that cause exit
import warnings
warnings.filterwarnings('ignore', category=UserWarning)

import uuid, os, tempfile, logging, json, pathlib, re, time, atexit, hashlib, ipaddress
from datetime import datetime, timezone, timedelta
from typing import Tuple, List, Optional
from flask import Flask, render_template, request, make_response, session, abort
from botocore.exceptions import BotoCoreError, ClientError
from botocore.config import Config
import boto3
import dotenv
import pymupdf4llm
from trp import Document

# Load environment variables from .env or .env.default
if not dotenv.load_dotenv():
    dotenv.load_dotenv('.env.default')

# Configure logging based on Flask debug mode
logger = logging.getLogger(__name__)
def configure_logging():
    log_level = logging.DEBUG if app.debug else logging.INFO
    logging.basicConfig(level=log_level,
            format=os.getenv('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))


debug_mode = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
app = Flask(__name__, static_url_path='/static', static_folder='static') # or app = Flask(__name__)

# Suppress broken pipe errors from client disconnections (harmless warnings)
logging.getLogger('werkzeug').setLevel(logging.ERROR)

# Suppress BrokenPipeError at the OS signal level (macOS/Linux)
try:
    import signal
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except (AttributeError, ValueError):
    pass  # Windows doesn't have SIGPIPE

def get_int_env(key: str, default: int) -> int:
    """Safely get integer from environment variable, stripping comments and whitespace."""
    value = os.getenv(key)
    if value is None:
        return default
    # Strip comments (anything after #), whitespace, and quotes
    value = value.split('#')[0].strip().strip('\'"')
    try:
        return int(value)
    except ValueError:
        logger.warning(f"Invalid integer value for {key}: {value}, using default: {default}")
        return default

app.config['SECRET_KEY'] = os.urandom(24)
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour session
app.config['MAX_CONTENT_LENGTH'] = get_int_env('MAX_CONTENT_LENGTH', 134217728)

# Load private evaluation rules
def load_evaluation_rules() -> dict:
    """Load evaluation rules from private JSON file, with fallback to default."""
    rules_path = pathlib.Path(__file__).parent / "evaluation-rules.json"
    default_rules_path = pathlib.Path(__file__).parent / "evaluation-rules.default.json"

    # Try to load custom rules
    if rules_path.exists():
        try:
            with open(rules_path, 'r') as f:
                logger.info(f"Loaded evaluation rules from {rules_path}")
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading evaluation-rules.json: {str(e)}")
            logger.info("Attempting to load default rules instead...")

    # If custom rules don't exist or failed to load, try default
    if default_rules_path.exists():
        try:
            with open(default_rules_path, 'r') as f:
                logger.info(f"Loaded default evaluation rules from {default_rules_path}")
                rules = json.load(f)

                # Copy default rules to evaluation-rules.json for future use
                try:
                    with open(rules_path, 'w') as out_f:
                        json.dump(rules, out_f, indent=2)
                    logger.info(f"Created evaluation-rules.json from default rules at {rules_path}")
                except Exception as e:
                    logger.warning(f"Could not create evaluation-rules.json: {str(e)}")

                return rules
        except Exception as e:
            logger.error(f"Error loading evaluation-rules.default.json: {str(e)}")

    # If all else fails, return empty dict with warning
    logger.warning(f"Neither evaluation-rules.json nor evaluation-rules.default.json found. Using empty rules.")
    return {}

evaluation_rules = load_evaluation_rules()


def get_bedrock_client():
    """Initialize Bedrock client with local credentials and retry configuration"""
    try:
        session = boto3.Session()
        region = session.region_name or os.getenv('AWS_REGION', 'us-west-2')
        
        # Configure retry behavior
        retry_config = Config(
            retries={
                "max_attempts": get_int_env('MAX_RETRIES', 10),
                "mode": "standard",
            }
        )
        
        # Create Bedrock client using local credentials
        client = session.client(
            service_name='bedrock-runtime',
            region_name=region,
            config=retry_config
        )
        
        return client
    except (BotoCoreError, ClientError) as e:
        app.logger.error(f"Failed to initialize Bedrock client: {str(e)}")
        raise

# Initialize Bedrock client
bedrock = get_bedrock_client()

# Global S3 bucket name for Textract (created on-demand, deleted on shutdown)
textract_bucket_name = None

def get_textract_bucket_name():
    """Get or create S3 bucket name for Textract operations"""
    global textract_bucket_name
    if textract_bucket_name is None:
        app_name = os.getenv('APP_NAME', 'spectater').lower()
        account_id = boto3.client('sts').get_caller_identity()['Account']
        session = boto3.session.Session()
        region = session.region_name or os.getenv('AWS_REGION', 'us-west-2')
        textract_bucket_name = f'{app_name}-textract-{account_id}-{region}'
    return textract_bucket_name

def ensure_s3_bucket():
    """Create S3 bucket if it doesn't exist"""
    bucket_name = get_textract_bucket_name()
    s3 = boto3.client('s3')

    try:
        s3.head_bucket(Bucket=bucket_name)
        logger.info(f"Using existing Textract bucket: {bucket_name}")
    except ClientError:
        logger.info(f"Creating Textract bucket: {bucket_name}")
        try:
            session = boto3.session.Session()
            region = session.region_name or os.getenv('AWS_REGION', 'us-west-2')

            if region == 'us-east-1':
                s3.create_bucket(Bucket=bucket_name)
            else:
                s3.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': region}
                )
            logger.info(f"Created Textract bucket: {bucket_name}")
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            # Handle race condition where bucket is being created by another process
            if error_code in ['BucketAlreadyOwnedByYou', 'OperationAborted', 'BucketAlreadyExists']:
                logger.info(f"Bucket creation race condition detected, bucket already exists or in progress: {bucket_name}")
                # Wait a moment and verify bucket exists
                import time
                time.sleep(1)
                try:
                    s3.head_bucket(Bucket=bucket_name)
                    logger.info(f"Bucket confirmed exists: {bucket_name}")
                except:
                    logger.warning(f"Bucket check failed, but continuing: {bucket_name}")
            else:
                raise

    return bucket_name

def cleanup_textract_bucket():
    """Delete Textract bucket and all objects on shutdown"""
    global textract_bucket_name
    if textract_bucket_name is None:
        return

    s3 = boto3.client('s3')
    try:
        logger.info(f"Cleaning up Textract bucket: {textract_bucket_name}")

        # Delete all objects first
        paginator = s3.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=textract_bucket_name):
            if 'Contents' in page:
                objects = [{'Key': obj['Key']} for obj in page['Contents']]
                s3.delete_objects(Bucket=textract_bucket_name, Delete={'Objects': objects})

        # Delete the bucket
        s3.delete_bucket(Bucket=textract_bucket_name)
        logger.info(f"Deleted Textract bucket: {textract_bucket_name}")
    except ClientError as e:
        logger.error(f"Failed to cleanup Textract bucket: {str(e)}")

# Register cleanup on shutdown
atexit.register(cleanup_textract_bucket)

def validate_file_type(file, allowed_extensions=('.pdf', '.txt', '.md')) -> None:
    """Validate uploaded file type"""
    filename = file.filename.lower()
    if not filename.endswith(allowed_extensions):
        ext_names = ', '.join(ext.upper().replace('.', '') for ext in allowed_extensions)
        raise ValueError(f"Invalid file type: {filename}. Allowed: {ext_names}")

def get_session_id():
    """Get or create session ID"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
        session.permanent = True
    return session['session_id']

def get_session_cache_dir(session_id: str) -> pathlib.Path:
    """Get cache directory for session"""
    cache_base = pathlib.Path(os.getenv('CACHE_DIR', 'cache'))
    session_dir = cache_base / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir

def get_policy_cache_path(session_id: str) -> pathlib.Path:
    """Get path to session's cached policy file"""
    return get_session_cache_dir(session_id) / "policy.md"

def save_policy_to_cache(text: str, session_id: str):
    """Save policy text to session-specific cache"""
    cache_path = get_policy_cache_path(session_id)
    cache_path.write_text(text)
    logger.debug(f"Saved policy to cache: {cache_path}")

def get_cached_policy(session_id: str) -> Optional[str]:
    """Get cached policy text for session"""
    cache_path = get_policy_cache_path(session_id)
    if cache_path.exists():
        logger.debug(f"Policy cache hit: {cache_path}")
        return cache_path.read_text()
    return None

def save_submission_to_cache(text: str, session_id: str, filename: str):
    """Save submission text to session-specific cache (debug mode only)"""
    if not app.debug:
        return

    cache_dir = get_session_cache_dir(session_id)
    # Create safe filename using hash of the original filename
    file_hash = hashlib.md5(filename.encode()).hexdigest()[:8]
    cache_path = cache_dir / f"submission_{file_hash}.md"
    cache_path.write_text(text)
    logger.debug(f"Saved submission '{filename}' to cache: {cache_path}")

def get_cached_submission(session_id: str, filename: str) -> Optional[str]:
    """Get cached submission text for session (debug mode only)"""
    if not app.debug:
        return None

    cache_dir = get_session_cache_dir(session_id)
    file_hash = hashlib.md5(filename.encode()).hexdigest()[:8]
    cache_path = cache_dir / f"submission_{file_hash}.md"
    if cache_path.exists():
        logger.debug(f"Submission cache hit for '{filename}': {cache_path}")
        return cache_path.read_text()
    return None

def _html_table_to_md(match):
    """Convert HTML tables to markdown with alignment detection"""
    table_html = match.group(0)
    table = pymupdf4llm.Table(table_html)

    # Build header separator with alignment
    alignments = ["---"] * len(table.headers)
    for i, col in enumerate(table.columns):
        if col.alignment == pymupdf4llm.Alignment.CENTER:
            alignments[i] = ":---:"
        elif col.alignment == pymupdf4llm.Alignment.RIGHT:
            alignments[i] = "---:"

    # Build pipe-formatted table
    rows = ["|".join(table.headers)]
    rows.append("|".join(alignments))
    for row in table.rows:
        rows.append("|".join(cell.text.replace('\n', ' ') for cell in row))

    return "\n\n" + "|\n".join(rows) + "\n\n"

def analyze_pdf_with_textract(pdf_path: str) -> dict:
    """Analyze PDF using AWS Textract via S3"""
    bucket_name = ensure_s3_bucket()
    s3 = boto3.client('s3')
    textract = boto3.client('textract')

    # Ensure textract folder exists
    textract_dir = pathlib.Path('textract')
    textract_dir.mkdir(exist_ok=True)

    # Upload to S3
    file_name = pathlib.Path(pdf_path).name
    object_key = f'documents/{uuid.uuid4()}/{file_name}'

    logger.info(f"Uploading {file_name} to S3 for Textract analysis")
    s3.upload_file(pdf_path, bucket_name, object_key)

    try:
        # Start async Textract job
        logger.info("Starting Textract analysis job")
        response = textract.start_document_analysis(
            DocumentLocation={'S3Object': {'Bucket': bucket_name, 'Name': object_key}},
            FeatureTypes=['TABLES', 'FORMS', 'LAYOUT']
        )
        job_id = response['JobId']

        # Poll for completion
        logger.info(f"Waiting for Textract job {job_id} to complete")
        while True:
            response = textract.get_document_analysis(JobId=job_id)
            status = response['JobStatus']

            if status == 'SUCCEEDED':
                break
            elif status == 'FAILED':
                raise Exception(f"Textract job failed: {response.get('StatusMessage', 'Unknown error')}")

            time.sleep(5)

        # Collect all pages of results
        all_blocks = response['Blocks']
        next_token = response.get('NextToken')

        while next_token:
            response = textract.get_document_analysis(JobId=job_id, NextToken=next_token)
            all_blocks.extend(response['Blocks'])
            next_token = response.get('NextToken')

        logger.info(f"Textract analysis complete: {len(all_blocks)} blocks retrieved")

        # Save raw Textract output to textract folder
        textract_response = {'Blocks': all_blocks}
        output_filename = f"{pathlib.Path(file_name).stem}_textract_output.json"
        output_path = textract_dir / output_filename
        with open(output_path, 'w') as f:
            json.dump(textract_response, f, indent=2)
        logger.info(f"Saved Textract output to {output_path}")

        return textract_response

    finally:
        # Clean up S3 object
        try:
            s3.delete_object(Bucket=bucket_name, Key=object_key)
        except ClientError as e:
            logger.warning(f"Failed to delete S3 object: {str(e)}")

def convert_textract_to_markdown(response: dict) -> str:
    """Convert Textract response to Markdown"""
    doc = Document(response)
    markdown_content = ""

    for page_num, page in enumerate(doc.pages, start=1):
        if page_num > 1:
            markdown_content += f"\n---\n\n## Page {page_num}\n\n"

        # Get table cell positions to avoid duplicating text
        table_positions = set()
        for table in page.tables:
            for row in table.rows:
                for cell in row.cells:
                    if hasattr(cell, 'geometry') and cell.geometry:
                        bbox = cell.geometry.boundingBox
                        pos_key = (round(bbox.top, 4), round(bbox.left, 4), round(bbox.width, 4), round(bbox.height, 4))
                        table_positions.add(pos_key)

        # Add lines (text not in tables)
        for line in page.lines:
            if hasattr(line, 'geometry') and line.geometry:
                bbox = line.geometry.boundingBox
                line_key = (round(bbox.top, 4), round(bbox.left, 4), round(bbox.width, 4), round(bbox.height, 4))

                # Check if line overlaps with table
                in_table = False
                for table_pos in table_positions:
                    t_top, t_left, t_width, t_height = table_pos
                    l_top, l_left, l_width, l_height = line_key
                    if (t_top <= l_top <= t_top + t_height and t_left <= l_left <= t_left + t_width):
                        in_table = True
                        break

                if not in_table:
                    markdown_content += line.text + "\n\n"

        # Add tables
        for table_idx, table in enumerate(page.tables):
            markdown_content += f"### Table {table_idx + 1}\n\n"

            for r, row in enumerate(table.rows):
                row_text = "|"
                for cell in row.cells:
                    cell_text = cell.text.strip() if cell.text else ""
                    cell_text = cell_text.replace("|", "\\|").replace("\n", "<br>")
                    row_text += f" {cell_text} |"

                markdown_content += row_text + "\n"

                # Add separator after header row
                if r == 0:
                    separator = "|" + " --- |" * len(row.cells)
                    markdown_content += separator + "\n"

            markdown_content += "\n"

    return markdown_content

def extract_text_from_file(uploaded_file, reject_tables=False, use_textract_for_tables=False) -> str:
    """Extract text with table preservation using validated parameters"""
    temp_path = None
    try:
        filename = uploaded_file.filename
        with tempfile.NamedTemporaryFile(suffix=pathlib.Path(filename).suffix, delete=False) as tmp:
            uploaded_file.save(tmp.name)
            temp_path = tmp.name

            if filename.lower().endswith('.pdf'):
                # First, try to detect if PDF is image-based by checking for any extractable text
                import fitz
                doc = fitz.open(temp_path)
                is_image_pdf = True
                page_count = len(doc)

                for page in doc:
                    text = page.get_text().strip()
                    if text:
                        is_image_pdf = False
                        break
                doc.close()

                # If it's image-based, use Textract directly
                if is_image_pdf and page_count > 0:
                    logger.info(f"Document '{filename}' appears to be image-based. Using AWS Textract for OCR.")
                    try:
                        textract_response = analyze_pdf_with_textract(temp_path)
                        markdown_text = convert_textract_to_markdown(textract_response)
                        logger.info(f"Textract OCR analysis complete for '{filename}'")
                    except Exception as textract_error:
                        logger.error(f"Textract failed for '{filename}': {str(textract_error)}")
                        raise ValueError(f"Failed to extract text from '{filename}' using both standard methods and OCR: {str(textract_error)}")
                else:
                    # Try standard extraction methods for text-based PDFs
                    try:
                        # Try primary extraction with table strategy
                        try:
                            markdown_text = pymupdf4llm.to_markdown(
                                doc=temp_path,
                                table_strategy="lines_strict",
                                write_images=False,
                                force_text=True,
                                margins=0
                            )
                        except Exception as inner_e:
                            # If table strategy fails, try simpler approach
                            logger.debug(f"pymupdf4llm with table_strategy failed: {inner_e}. Retrying with default strategy.")
                            markdown_text = pymupdf4llm.to_markdown(
                                doc=temp_path,
                                write_images=False,
                                force_text=True
                            )
                    except Exception as e:
                        # Fallback to PyMuPDF extraction if pymupdf4llm fails
                        logger.warning(f"pymupdf4llm failed for '{filename}': {str(e)}. Trying fallback extraction.")
                        doc = fitz.open(temp_path)
                        markdown_text = ""
                        for page_num, page in enumerate(doc, start=1):
                            if page_num > 1:
                                markdown_text += f"\n---\n\n## Page {page_num}\n\n"
                            # Try multiple text extraction methods
                            text = page.get_text()
                            if not text.strip():
                                # Try alternate extraction with layout preservation
                                text = page.get_text("blocks")
                                if isinstance(text, list):
                                    text = "\n".join(block[4] for block in text if len(block) > 4 and isinstance(block[4], str))
                            if not text.strip():
                                # Try with dict format for more detailed extraction
                                text = page.get_text("dict")
                                if isinstance(text, dict) and "blocks" in text:
                                    text = "\n".join(block.get("text", "") for block in text["blocks"] if block.get("text"))
                            markdown_text += text
                        doc.close()

                # Check for empty text (scanned image-only PDF) or tables
                is_empty_text = len(markdown_text.strip()) == 0
                has_html_tables = bool(re.search(r'<table\b[^>]*>.*?</table>', markdown_text, flags=re.DOTALL|re.IGNORECASE))
                has_md_tables = bool(re.search(r'\|.*\|.*\n\|[\s:|-]+\|', markdown_text))

                # Use Textract for scanned PDFs (empty text) or PDFs with tables
                if is_empty_text or has_html_tables or has_md_tables:
                    if is_empty_text and not use_textract_for_tables:
                        # Auto-enable Textract for scanned documents
                        logger.info(f"Document '{filename}' appears to be scanned (no extractable text). Automatically using AWS Textract for OCR analysis.")
                        use_textract_for_tables = True

                    if reject_tables and (has_html_tables or has_md_tables):
                        raise ValueError(f"Document '{filename}' contains tables which are too complex to process. Please upload a document without tables.")
                    elif use_textract_for_tables:
                        # Use Textract for complex PDFs with tables or scanned documents
                        reason = "scanned image content" if is_empty_text else "tables"
                        logger.info(f"Document '{filename}' contains {reason}. Using AWS Textract for OCR analysis.")
                        textract_response = analyze_pdf_with_textract(temp_path)
                        markdown_text = convert_textract_to_markdown(textract_response)
                        logger.info(f"Textract OCR analysis complete for '{filename}'")

                        # Apply character limit if configured
                        max_chars = get_int_env('MAX_CHARS_PER_DOC', 0)
                        if max_chars > 0 and len(markdown_text) > max_chars:
                            original_length = len(markdown_text)
                            markdown_text = markdown_text[:max_chars]
                            logger.info(f"Truncated document '{filename}' from {original_length} to {max_chars} characters")

                        return markdown_text
            else:
                # Direct text file handling
                with open(temp_path, 'r', encoding='utf-8') as f:
                    markdown_text = f.read()

            # Enhanced table pattern match
            markdown_text = re.sub(
                r'<table\b[^>]*>.*?</table>',  # More precise HTML table matching
                _html_table_to_md,
                markdown_text,
                flags=re.DOTALL|re.IGNORECASE
            )

            # Apply character limit if configured
            max_chars = get_int_env('MAX_CHARS_PER_DOC', 0)
            if max_chars > 0 and len(markdown_text) > max_chars:
                original_length = len(markdown_text)
                markdown_text = markdown_text[:max_chars]
                logger.info(f"Truncated document '{filename}' from {original_length} to {max_chars} characters")

            logger.debug(f"Extracted structured text from {filename}")
            return markdown_text

    except Exception as e:
        logger.error(f"Processing failed for {filename}: {str(e)}")
        raise ValueError(f"Document processing error: {e}")
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

def evaluate_requirements(policy_text: str, submission_text: str) -> Tuple[str, str]:
    """
    Evaluate if a submission document meets the requirements in a policy document.
    
    Args:
        policy_text: Text content of the policy document
        submission_text: Text content of the submission document
        
    Returns:
        Tuple[str, str]: (result status, explanation if status is YELLOW)
        
    Raises:
        BotoCoreError: If AWS Bedrock API call fails
        ValueError: If response parsing fails
    """
    # Read prompt template from file
    prompt_path = pathlib.Path(__file__).parent / "analysis-prompt.md"
    with open(prompt_path, 'r') as f:
        analysis_prompt = f.read()

    # Inject private evaluation rules into the prompt
    if evaluation_rules:
        rules_injection = "\n\n**EVALUATION RULES (Loaded from Configuration):**\n"

        # Add Certificate Holder Name variants
        if 'certificate_holder_name' in evaluation_rules:
            variants = evaluation_rules['certificate_holder_name'].get('acceptable_variants', [])
            if variants:
                rules_injection += f"- Certificate Holder Name variants: {', '.join(variants)}\n"

        # Add General Liability rules
        if 'general_liability' in evaluation_rules:
            gl_rules = evaluation_rules['general_liability']
            cgl_min = gl_rules.get('cgl_minimum_per_occurrence', 2000000)
            umbrella_required = gl_rules.get('umbrella_required_if_cgl_insufficient', True)
            combined_coverage = gl_rules.get('combined_coverage_logic', False)
            description = gl_rules.get('description', '')
            pass_conditions = gl_rules.get('pass_conditions', [])
            fail_conditions = gl_rules.get('fail_conditions', [])

            rules_injection += f"- **CRITICAL - CGL Per Occurrence Requirement**: Minimum ${cgl_min:,} per occurrence\n"
            rules_injection += f"- **CRITICAL - General Aggregate CANNOT substitute for per-occurrence**: Only per-occurrence limits apply\n"

            if combined_coverage:
                rules_injection += f"- **CRITICAL - COMBINED COVERAGE LOGIC ENABLED**: If CGL per occurrence < ${cgl_min:,}, the submission may still PASS if CGL + Umbrella together ≥ ${cgl_min:,} per occurrence. In this case, BOTH 3.5 (CGL) and 3.6 (Umbrella) PASS.\n"
            else:
                rules_injection += f"- **CRITICAL - Umbrella requirement**: If CGL per occurrence < ${cgl_min:,}, Umbrella is REQUIRED. If no Umbrella, FAIL both 3.5 and 3.6\n"

            if description:
                rules_injection += f"- {description}\n"

            if pass_conditions:
                rules_injection += "- **PASS CONDITIONS (When both 3.5 and 3.6 Pass):**\n"
                for pass_cond in pass_conditions:
                    rules_injection += f"  - {pass_cond}\n"

            if fail_conditions:
                rules_injection += "- **FAIL CONDITIONS:**\n"
                for fail_cond in fail_conditions:
                    rules_injection += f"  - {fail_cond}\n"

        # Add Address rules
        if 'certificate_holder_address' in evaluation_rules:
            addr_rules = evaluation_rules['certificate_holder_address']
            valid_addresses = addr_rules.get('valid_addresses', [])
            address_keywords = addr_rules.get('address_keywords', [])
            if valid_addresses:
                rules_injection += f"- **CRITICAL - Valid Certificate Holder Addresses (with format variations):**\n"
                for addr in valid_addresses:
                    rules_injection += f"  - {addr}\n"
                if address_keywords:
                    rules_injection += f"- **Address Keywords** (also acceptable, indicate same location): {', '.join(address_keywords)}\n"
                rules_injection += f"- Accept format variations like SW/Southwest, Ave/Avenue, St/Street, Blvd/Boulevard, MU/Memorial Union, etc.\n"
                rules_injection += f"- REJECT any address NOT matching one of these locations (accounting for format variations)\n"

        # Insert rules before the placeholder section
        analysis_prompt = analysis_prompt.replace(
            '**Policy Document:**',
            rules_injection + '\n**Policy Document:**'
        )

    # Replace placeholders (using replace instead of format to avoid issues with JSON braces)
    analysis_prompt = analysis_prompt.replace('{policy_text}', policy_text)
    analysis_prompt = analysis_prompt.replace('{submission_text}', submission_text)

    try:
        model_id = os.getenv('MODEL_ID', 'anthropic.claude-3-5-haiku-20241022-v1:0')

        # Calculate dynamic max_tokens based on input size
        # Use 2/3 of input bytes to ensure enough space for JSON output
        input_bytes = len(analysis_prompt.encode('utf-8'))
        calculated_max_tokens = (input_bytes * 2) // 3

        # Use configured MAX_TOKENS as a minimum/override, or use calculated value
        configured_max_tokens = get_int_env('MAX_TOKENS', 0)
        if configured_max_tokens > 0:
            max_tokens = max(configured_max_tokens, calculated_max_tokens)
        else:
            max_tokens = calculated_max_tokens

        # Ensure minimum of 5000 tokens for JSON output
        max_tokens = max(5000, max_tokens)

        if app.debug:
            print(f"[DEBUG] Input bytes: {input_bytes}, Calculated max_tokens: {calculated_max_tokens}, Final max_tokens: {max_tokens}")

        request_body = {
            "anthropic_version": os.getenv('ANTHROPIC_VERSION', 'bedrock-2023-05-31'),
            "max_tokens": max_tokens,
            "temperature": 0,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": analysis_prompt,
                            "cache_control": {"type": "ephemeral"}
                        }
                    ]
                }
            ]
        }

        # Add extended context window for Claude Sonnet 4 models with large token limits
        # Note: Claude Opus 4 doesn't support the context-1m-2025-08-07 beta flag
        if "claude-sonnet-4" in model_id and max_tokens > 200000:
            request_body["additionalModelRequestFields"] = {
                "anthropic_beta": ["context-1m-2025-08-07"]
            }
            logger.info(f"Added 1M token context window for Claude Sonnet 4 model: {model_id}")

        logger.debug(f"Bedrock request body: {json.dumps(request_body, indent=2)}")

        response = bedrock.invoke_model(
            modelId=model_id,
            body=json.dumps(request_body)
        )
        
        response_body = json.loads(response['body'].read())
        logger.debug(f"Bedrock response: {json.dumps(response_body, indent=2)}")
        
        # Extract text content from Claude 3's response structure
        content = response_body.get('content', [])
        if not content or not isinstance(content, list):
            logger.error(f"Unexpected response structure: {response_body}")
            raise ValueError("Response missing content array")
            
        # Get the text from the first content item
        text_content = next((item['text'] for item in content if item['type'] == 'text'), None)
        if not text_content:
            logger.error(f"No text content found in response: {response_body}")
            raise ValueError("Response missing text content")

        # Log first 100 chars of response in debug mode
        if app.debug:
            preview = text_content[:100].replace('\n', ' ')
            print(f"[DEBUG] LLM response preview (first 100 chars): {preview}")

        # Extract JSON from response - find the outermost JSON object
        # Method 1: Try with code blocks
        json_str = None
        json_match = re.search(r'```(?:json)?\s*\n?(\{[\s\S]*)\s*\n?```', text_content)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            # Method 2: Find JSON by counting braces to get complete structure
            start_idx = text_content.find('{')
            if start_idx != -1:
                brace_count = 0
                for i in range(start_idx, len(text_content)):
                    if text_content[i] == '{':
                        brace_count += 1
                    elif text_content[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_str = text_content[start_idx:i+1]
                            break

        if json_str:
            try:
                json_data = json.loads(json_str)

                # Count actual pass/fail/partial by iterating through requirements
                requirements = json_data.get('requirements', [])
                actual_passed = sum(1 for req in requirements if req.get('pass', False) and req.get('pass_status') != 'PARTIAL')
                actual_partial = sum(1 for req in requirements if req.get('pass', False) and req.get('pass_status') == 'PARTIAL')
                actual_failed = sum(1 for req in requirements if not req.get('pass', False))
                actual_total = len(requirements)

                # Get summary counts from JSON
                summary = json_data.get('summary', {})
                summary_total = summary.get('totalChecks', 0)
                summary_passed = summary.get('passed', 0)
                summary_partial = summary.get('partial', 0)
                summary_failed = summary.get('failed', 0)

                # Check for inconsistencies and auto-correct summary counts
                inconsistent = False
                if actual_total != summary_total or actual_passed != summary_passed or actual_failed != summary_failed or actual_partial != summary_partial:
                    inconsistent = True
                    logger.warning(f"JSON summary inconsistent! Summary says {summary_total} total, {summary_passed} passed, {summary_partial} partial, {summary_failed} failed, but requirements show {actual_total} total, {actual_passed} passed, {actual_partial} partial, {actual_failed} failed")

                    # Auto-correct the summary counts to match the actual array
                    logger.info(f"Auto-correcting summary counts to match requirements array")
                    json_data['summary']['totalChecks'] = actual_total
                    json_data['summary']['passed'] = actual_passed
                    json_data['summary']['partial'] = actual_partial
                    json_data['summary']['failed'] = actual_failed

                # Determine status based on actual pass/fail/partial in requirements (not summary)
                all_passed = all(req.get('pass', False) for req in requirements)
                has_partial = any(req.get('pass_status') == 'PARTIAL' for req in requirements)

                if all_passed and not has_partial:
                    status = "GREEN"
                elif has_partial and actual_failed == 0:
                    status = "YELLOW"
                else:
                    status = "RED"

                if app.debug:
                    print(f"[DEBUG] Parsed JSON with {actual_total} requirements")
                    print(f"[DEBUG] Actual counts: {actual_passed} passed, {actual_partial} partial, {actual_failed} failed")
                    print(f"[DEBUG] Summary counts: {summary_passed} passed, {summary_partial} partial, {summary_failed} failed")
                    print(f"[DEBUG] Status determined: {status}")
                    if inconsistent:
                        print(f"[DEBUG] WARNING: Inconsistent JSON summary! Check analysis-prompt.md or policy document.")

                # Return status and full response text for display
                return status, text_content

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from response: {e}")
                if app.debug:
                    print(f"[DEBUG] JSON Parse Error Details:")
                    print(f"[DEBUG] Error: {e}")
                    print(f"[DEBUG] JSON string that failed to parse:")
                    print("=" * 80)
                    print(json_str)
                    print("=" * 80)
                    # Show the area around the error
                    error_pos = e.pos if hasattr(e, 'pos') else 0
                    start = max(0, error_pos - 100)
                    end = min(len(json_str), error_pos + 100)
                    print(f"[DEBUG] Context around error position {error_pos}:")
                    print(json_str[start:end])
                    print(" " * (error_pos - start) + "^-- ERROR HERE")
                raise ValueError(f"Invalid JSON in response: {e}")
        else:
            logger.error(f"No JSON found in response: {text_content[:200]}")
            raise ValueError("Response does not contain required JSON structure")
            
    except (BotoCoreError, ClientError) as e:
        logger.error(f"Bedrock API error: {str(e)}")
        raise
    except (KeyError, json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse Bedrock response: {str(e)}")
        raise

def check_subnet_access():
    """Check if request is from allowed subnet"""
    subnet_only = os.getenv('SUBNET_ONLY', '127.0.0.1/32')
    if not subnet_only:
        return True  # No restriction if empty

    try:
        allowed_network = ipaddress.ip_network(subnet_only, strict=False)
        client_ip = ipaddress.ip_address(request.remote_addr)

        if client_ip not in allowed_network:
            logger.warning(f"Access denied for IP {client_ip} (allowed subnet: {subnet_only})")
            return False

        return True
    except (ValueError, AttributeError) as e:
        logger.error(f"Invalid SUBNET_ONLY configuration: {e}")
        return True  # Allow access if configuration is invalid

def load_static_requirements():
    """Load requirements from file if REQUIREMENTS env var is set"""
    requirements_file = os.getenv('REQUIREMENTS')
    if requirements_file and os.path.exists(requirements_file):
        try:
            with open(requirements_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to load requirements file {requirements_file}: {e}")
    return None

def load_introduction():
    """Load introduction text from file if INTRODUCTION env var is set"""
    intro_file = os.getenv('INTRODUCTION')
    if intro_file and os.path.exists(intro_file):
        try:
            with open(intro_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to load introduction file {intro_file}: {e}")
    return None

@app.route('/', methods=['GET', 'POST'])
def index():
    # Check subnet access restriction
    if not check_subnet_access():
        return """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Access Denied</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        </head>
        <body>
            <div class="container mt-5">
                <div class="alert alert-danger" role="alert">
                    <h4 class="alert-heading">Access Denied</h4>
                    <p>You are not authorized to access this application from your location.</p>
                    <p class="mb-0">You may need to connect via VPN with split tunneling DISABLED.</p>
                </div>
            </div>
        </body>
        </html>
        """, 403

    # Load configuration
    title = os.getenv('TITLE', 'Policy / Requirements Evaluator')
    introduction = load_introduction()
    static_requirements = load_static_requirements()

    if request.method == 'POST':
        if 'submission' not in request.files:
            return render_template('index.html', error="Submission document is required")
        
        submission_file = request.files['submission']
        if submission_file.filename == '':
            return render_template('index.html', error="Submission document is required")
            
        policy_file = request.files.get('policy')
        
        try:
            # Validate all policy files (PDF, TXT, MD allowed)
            for file in request.files.getlist('policy'):
                if file.filename:  # Skip empty files
                    validate_file_type(file, allowed_extensions=('.pdf', '.txt', '.md'))

            # Validate all submission files (PDF and MD allowed)
            for file in request.files.getlist('submission'):
                validate_file_type(file, allowed_extensions=('.pdf', '.md'))

            session_id = get_session_id()

            # Handle multiple policy files or use static requirements
            if static_requirements:
                # Use static requirements from file
                policy_text = static_requirements
                logger.debug("Using static requirements from file")
            else:
                # Handle uploaded policy files
                policy_text = ""
                if policy_files := request.files.getlist('policy'):
                    for file in policy_files:
                        if file.filename:  # Skip empty files
                            policy_text += "\n" + extract_text_from_file(file)
                    if policy_text:
                        save_policy_to_cache(policy_text.strip(), session_id)
                    else:
                        # Try to load cached policy
                        policy_text = get_cached_policy(session_id)
                        if not policy_text:
                            return render_template('index.html',
                                                 title=title,
                                                 introduction=introduction,
                                                 static_requirements=static_requirements,
                                                 error="No policy document available. Please upload one.")
                        logger.debug("Using cached policy document")

            # Handle multiple submission files
            submission_text = ""
            if submission_files := request.files.getlist('submission'):
                for file in submission_files:
                    if file.filename:
                        # Check cache first in debug mode
                        cached_text = get_cached_submission(session_id, file.filename)
                        if cached_text:
                            if app.debug:
                                print(f"[DEBUG] Using cached submission for {file.filename}")
                            submission_text += "\n" + cached_text
                        else:
                            extracted_text = extract_text_from_file(file, reject_tables=False, use_textract_for_tables=True)
                            submission_text += "\n" + extracted_text
                            # Save to cache in debug mode
                            save_submission_to_cache(extracted_text, session_id, file.filename)
            else:
                return render_template('index.html', error="At least one submission document is required")
            submission_text = submission_text.strip()
            
            result, raw_response = evaluate_requirements(policy_text, submission_text)
            logger.info(f"Evaluation result: {result}")

            # Extract JSON from response (already done in evaluate_requirements)
            json_output = None
            json_data = None
            try:
                if app.debug:
                    print(f"[DEBUG] Full raw response ({len(raw_response)} chars):")
                    print("=" * 80)
                    print(raw_response)
                    print("=" * 80)

                # Extract JSON using brace counting for complete structure
                json_match = re.search(r'```(?:json)?\s*\n?(\{[\s\S]*)\s*\n?```', raw_response)
                if json_match:
                    json_output = json_match.group(1).strip()
                else:
                    # Find JSON by counting braces
                    start_idx = raw_response.find('{')
                    if start_idx != -1:
                        brace_count = 0
                        for i in range(start_idx, len(raw_response)):
                            if raw_response[i] == '{':
                                brace_count += 1
                            elif raw_response[i] == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    json_output = raw_response[start_idx:i+1]
                                    break

                if json_output:
                    if app.debug:
                        print(f"[DEBUG] Extracted JSON string ({len(json_output)} chars):")
                        print(json_output)

                    json_data = json.loads(json_output)

                    # Verify consistency by counting actual pass/fail
                    requirements = json_data.get('requirements', [])
                    actual_passed = sum(1 for req in requirements if req.get('pass', False) and req.get('pass_status') != 'PARTIAL')
                    actual_partial = sum(1 for req in requirements if req.get('pass', False) and req.get('pass_status') == 'PARTIAL')
                    actual_failed = sum(1 for req in requirements if not req.get('pass', False))
                    actual_total = len(requirements)

                    summary = json_data.get('summary', {})
                    summary_total = summary.get('totalChecks', 0)
                    summary_passed = summary.get('passed', 0)
                    summary_partial = summary.get('partial', 0)
                    summary_failed = summary.get('failed', 0)

                    inconsistent_warning = None
                    if actual_total != summary_total or actual_passed != summary_passed or actual_failed != summary_failed or actual_partial != summary_partial:
                        inconsistent_warning = (
                            f"ℹ️ Note: Summary counts were auto-corrected to match requirements array. "
                            f"Corrected to {actual_total} total ({actual_passed} passed, {actual_partial} partial, {actual_failed} failed)."
                        )
                        logger.info(inconsistent_warning)

                    if app.debug:
                        print(f"[DEBUG] Successfully parsed JSON!")
                        print(f"[DEBUG] Actual counts: {actual_passed} passed, {actual_failed} failed (total: {actual_total})")
                        print(f"[DEBUG] Summary counts: {summary_passed} passed, {summary_failed} failed (total: {summary_total})")
                        if inconsistent_warning:
                            print(f"[DEBUG] {inconsistent_warning}")

            except (json.JSONDecodeError, AttributeError) as e:
                if app.debug:
                    print(f"[DEBUG] JSON extraction/parsing failed: {e}")
                    if json_output:
                        print(f"[DEBUG] Failed JSON string was:")
                        print(json_output)
                inconsistent_warning = None

            # Return response
            model_id = os.getenv('MODEL_ID', 'anthropic.claude-3-5-haiku-20241022-v1:0')
            submission_filename = request.form.get('submissionFileName', '')
            return render_template('index.html',
                                 title=title,
                                 introduction=introduction,
                                 static_requirements=static_requirements,
                                 result=result,
                                 explanation=raw_response,
                                 json_data=json_output,
                                 json_parsed=json_data,
                                 inconsistent_warning=inconsistent_warning,
                                 model_id=model_id,
                                 submission_filename=submission_filename)
            
        except Exception as e:
            logger.error(f"Error processing request: {str(e)}")
            return render_template('index.html',
                                 title=title,
                                 introduction=introduction,
                                 static_requirements=static_requirements,
                                 error=str(e))

    return render_template('index.html',
                         title=title,
                         introduction=introduction,
                         static_requirements=static_requirements)


@app.route('/guide')
def guide():
    """Display the 'How to Write Requirements' guide"""
    # Check subnet access restriction
    if not check_subnet_access():
        return """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Access Denied</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        </head>
        <body>
            <div class="container mt-5">
                <div class="alert alert-danger" role="alert">
                    <h4 class="alert-heading">Access Denied</h4>
                    <p>You are not authorized to access this application from your location.</p>
                    <p class="mb-0">You may need to connect via VPN with split tunneling DISABLED.</p>
                </div>
            </div>
        </body>
        </html>
        """, 403

    return render_template('guide.html')


@app.route('/download/template')
def download_template():
    """Download the requirements template as markdown"""
    # Check subnet access restriction
    if not check_subnet_access():
        abort(403)

    template_path = pathlib.Path(__file__).parent / "osu-requirements-template.md"
    if not template_path.exists():
        abort(404)

    try:
        with open(template_path, 'r') as f:
            content = f.read()

        response = make_response(content)
        response.headers['Content-Disposition'] = 'attachment; filename="osu-requirements-template.md"'
        response.headers['Content-Type'] = 'text/markdown; charset=utf-8'
        return response
    except Exception as e:
        logger.error(f"Error downloading template: {str(e)}")
        abort(500)


if __name__ == '__main__':
    # Prevent multiprocessing issues on exit
    import multiprocessing
    multiprocessing.set_start_method('fork', force=True)

    ssl_cert = os.getenv('SSL_CERT')
    ssl_key = os.getenv('SSL_KEY')
    ssl_context = None
    if ssl_cert and ssl_key:
        if os.path.exists(os.path.expanduser(ssl_cert)) and os.path.exists(os.path.expanduser(ssl_key)):
            ssl_context = (os.path.expanduser(ssl_cert), os.path.expanduser(ssl_key))
            print(f" * Starting with SSL using cert: {ssl_cert}")
        else:
            print(" * Warning: SSL certificate files specified but not found - starting without SSL")
            if not os.path.exists(os.path.expanduser(ssl_cert)):
                print(f"     Missing certificate file: {ssl_cert}")
            if not os.path.exists(os.path.expanduser(ssl_key)):
                print(f"     Missing key file: {ssl_key}")

    try:
        app.run(
            host='0.0.0.0',
            port=int(os.getenv('FLASK_PORT', 5000)),
            debug=debug_mode,
            ssl_context=ssl_context,
            use_reloader=False,
            threaded=True
        )
    except Exception as e:
        logger.error(f"Flask crashed with error: {e}")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

