#! /usr/bin/env python3

import uuid, os, tempfile, logging, json, pathlib, re
from datetime import datetime, timezone, timedelta
from typing import Tuple, List, Optional
from flask import Flask, render_template, request, make_response
from botocore.exceptions import BotoCoreError, ClientError
from botocore.config import Config
import boto3
import dotenv
import pymupdf4llm

# Load environment variables
dotenv.load_dotenv()

# Configure logging based on Flask debug mode
logger = logging.getLogger(__name__)
def configure_logging():
    log_level = logging.DEBUG if app.debug else logging.INFO
    logging.basicConfig(level=log_level, 
            format=os.getenv('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))


debug_mode = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
app = Flask(__name__, static_url_path='/static', static_folder='static') # or app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour session
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 134217728))


def get_bedrock_client():
    """Initialize Bedrock client with local credentials and retry configuration"""
    try:
        session = boto3.Session()
        region = session.region_name or os.getenv('AWS_REGION', 'us-west-2')
        
        # Configure retry behavior
        retry_config = Config(
            retries={
                "max_attempts": int(os.getenv('MAX_RETRIES', 10)),
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

def validate_file_type(file) -> None:
    """Validate uploaded file type"""
    filename = file.filename.lower()
    allowed_extensions = ('.pdf', '.txt', '.html', '.md')
    if not filename.endswith(allowed_extensions):
        raise ValueError(f"Invalid file type: {filename}. Allowed: PDF, TXT, HTML, MD")

def get_user_id():
    """Get or create user ID from cookie"""
    user_id = request.cookies.get(os.getenv('COOKIE_NAME', 'user_id'))
    if not user_id:
        user_id = str(uuid.uuid4())
    return user_id

def get_policy_cache_path(user_id: str) -> pathlib.Path:
    """Get path to user's cached policy file"""
    return pathlib.Path(os.getenv('CACHE_DIR', 'policy_cache')) / f"policy_{user_id}.txt"

def save_policy_to_cache(text: str, user_id: str):
    """Save policy text to user-specific cache"""
    os.makedirs(os.getenv('CACHE_DIR', 'policy_cache'), exist_ok=True)
    cache_path = get_policy_cache_path(user_id)
    cache_path.write_text(text)
    logger.debug(f"Saved policy to cache: {cache_path}")

def get_cached_policy(user_id: str) -> Optional[str]:
    """Get cached policy text for user"""
    cache_path = get_policy_cache_path(user_id)
    if cache_path.exists():
        logger.debug(f"Policy cache hit: {cache_path}")
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

def extract_text_from_file(uploaded_file) -> str:
    """Extract text with table preservation using validated parameters"""
    try:
        filename = uploaded_file.filename
        with tempfile.NamedTemporaryFile(suffix=pathlib.Path(filename).suffix, delete=False) as tmp:
            uploaded_file.save(tmp.name)
            temp_path = tmp.name
            
            if filename.lower().endswith('.pdf'):
                # Process with validated table parameters
                markdown_text = pymupdf4llm.to_markdown(
                doc=temp_path,  # Correct parameter name per docs
                table_strategy="lines_strict",  # Explicit table detection
                graphics_limit=10000,  # Handle complex technical docs
                write_images=False,  # Disable image processing
                force_text=True,  # Ensure text overlaps are preserved
                margins=0,  # Process full page content
                image_size_limit=0,  # Include all graphics as text
                extract_words=False  # Disable word coordinates
            )
            
            # Enhanced table pattern match
            markdown_text = re.sub(
                r'<table\b[^>]*>.*?</table>',  # More precise HTML table matching
                _html_table_to_md,
                markdown_text,
                flags=re.DOTALL|re.IGNORECASE
            )
            
            logger.debug(f"Extracted structured text from {filename}")
            return markdown_text
            
    except Exception as e:
        logger.error(f"Processing failed for {filename}: {str(e)}")
        raise ValueError(f"Document processing error: {e}")
    finally:
        if os.path.exists(temp_path):
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
    prompt_path = pathlib.Path(__file__).parent / "analysis-prompt.txt"
    with open(prompt_path, 'r') as f:
        analysis_prompt = f.read().format(
            policy_text=policy_text,
            submission_text=submission_text
        )

    try:
        request_body = {
            "anthropic_version": os.getenv('ANTHROPIC_VERSION', 'bedrock-2023-05-31'),
            "max_tokens": int(os.getenv('MAX_TOKENS', 100000)),
            "temperature": float(os.getenv('TEMPERATURE', 1.0)),
            "messages": [
                {
                    "role": "user",
                    "content": analysis_prompt
                }
            ]
        }
        logger.debug(f"Bedrock request body: {json.dumps(request_body, indent=2)}")
        
        response = bedrock.invoke_model(
            modelId=os.getenv('MODEL_ID', 'anthropic.claude-3-5-haiku-20241022-v1:0'),
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
            
        # Process the response text
        # Extract status (GREEN, YELLOW, ORANGE, RED) from the response
        text_upper = text_content.upper()
        for possible_status in ["GREEN", "YELLOW", "ORANGE", "RED"]:
            if possible_status in text_upper:
                status = possible_status
                # Remove the status word from the explanation
                explanation = text_content.replace(possible_status, "", 1).strip()
                # Remove any leading punctuation
                explanation = explanation.lstrip(".:- \n")
                break
        else:
            logger.error(f"No valid status found in response: {text_content}")
            raise ValueError("No valid status found in response")
        
        if status in ["GREEN", "YELLOW", "ORANGE", "RED"]:
            return status, explanation
        else:
            logger.error(f"Unexpected status in response: {text_content}")
            raise ValueError(f"Invalid status in response: {status}")
            
    except (BotoCoreError, ClientError) as e:
        logger.error(f"Bedrock API error: {str(e)}")
        raise
    except (KeyError, json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse Bedrock response: {str(e)}")
        raise

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'submission' not in request.files:
            return render_template('index.html', error="Submission document is required")
        
        submission_file = request.files['submission']
        if submission_file.filename == '':
            return render_template('index.html', error="Submission document is required")
            
        policy_file = request.files.get('policy')
        
        try:
            # Validate all policy files
            for file in request.files.getlist('policy'):
                if file.filename:  # Skip empty files
                    validate_pdf_file(file)
            
            # Validate all submission files
            for file in request.files.getlist('submission'):
                validate_pdf_file(file)

            user_id = get_user_id()
            
            # Handle multiple policy files
            policy_text = ""
            if policy_files := request.files.getlist('policy'):
                for file in policy_files:
                    if file.filename:  # Skip empty files
                        policy_text += "\n" + extract_text_from_file(file)
                if policy_text:
                    save_policy_to_cache(policy_text.strip(), user_id)
                else:
                    # Try to load cached policy
                    policy_text = get_cached_policy(user_id)
                    if not policy_text:
                        return render_template('index.html', error="No policy document available. Please upload one.")
                    logger.debug("Using cached policy document")

            # Handle multiple submission files
            submission_text = ""
            if submission_files := request.files.getlist('submission'):
                for file in submission_files:
                    if file.filename:
                        submission_text += "\n" + extract_text_from_file(file)
            else:
                return render_template('index.html', error="At least one submission document is required")
            submission_text = submission_text.strip()
            
            result, explanation = evaluate_requirements(policy_text, submission_text)
            logger.info(f"Evaluation result: {result}, Explanation: {explanation}")
            
            # Create response with cookie
            response = make_response(render_template('index.html', 
                                                   result=result, 
                                                   explanation=explanation))
            expires = datetime.now(timezone.utc) + timedelta(seconds=int(os.getenv('COOKIE_MAX_AGE', '2592000')))
            response.set_cookie(os.getenv('COOKIE_NAME', 'user_id'), user_id, expires=expires)
            return response
            
        except Exception as e:
            logger.error(f"Error processing request: {str(e)}")
            return render_template('index.html', error=str(e))
    
    return render_template('index.html')


if __name__ == '__main__':
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
    
    app.run(
        host='0.0.0.0',
        port=int(os.getenv('FLASK_PORT', 5000)),
        debug=debug_mode,
        ssl_context=ssl_context
    )

