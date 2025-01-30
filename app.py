#! /usr/bin/env python3

import uuid, os, tempfile, logging, json, pathlib
from datetime import datetime, timezone, timedelta
from typing import Tuple, List, Optional
from flask import Flask, render_template, request, make_response
from botocore.exceptions import BotoCoreError, ClientError
from botocore.config import Config
import boto3
import dotenv
import markitdown

# Load environment variables
dotenv.load_dotenv()

# Configure logging based on Flask debug mode
logger = logging.getLogger(__name__)
def configure_logging():
    log_level = logging.DEBUG if app.debug else logging.INFO
    logging.basicConfig(level=log_level, 
            format=os.getenv('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))


debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
app = Flask(__name__, static_url_path='/static', static_folder='static') # or app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour session
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 16777216))


def get_bedrock_client():
    """Initialize Bedrock client with local credentials and retry configuration"""
    try:
        session = boto3.Session()
        region = session.region_name or os.getenv('BEDROCK_REGION', 'us-west-2')
        
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

def extract_text_from_pdf(pdf_file) -> str:
    """
    Extract text content from a PDF file using MarkItDown.
    
    Args:
        pdf_file: File object containing PDF data
        
    Returns:
        str: Extracted text from the PDF in markdown format
        
    Raises:
        Exception: If PDF parsing fails
    """
    
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
        pdf_file.save(temp_file.name)
        temp_path = temp_file.name
    
    try:
        md = markitdown.MarkItDown()
        result = md.convert(temp_path)
        return result.text_content
    finally:
        # Clean up temporary file
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
    # Create simple analysis prompt with full documents
    analysis_prompt = f"""Human: Compare these two documents and determine if the 
    submission document meets the requirements specified in the policy document,

Policy Document:
{policy_text}

Submission Document:
{submission_text}

Based on all these comparisons, respond with exactly one word (GREEN, YELLOW, ORANGE or RED).
In addition provide an explanation on how specific requirements are met (GREEN) or may not be met.

GREEN means all requirements (quantifiable/numerical and unquantifiable) are fully met 
YELLOW means all quantifiable/numerical requirements are met but other requirements are ambiguous.
ORANGE means both numerical and other requirements are ambiguous and need clarification.
RED means one or more requirements are clearly not met.

""" 
    
    try:
        request_body = {
            "anthropic_version": os.getenv('ANTHROPIC_VERSION', 'bedrock-2023-05-31'),
            "max_tokens": int(os.getenv('MAX_TOKENS', 100000)),
            "temperature": float(os.getenv('TEMPERATURE', 0.7)),
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
            user_id = get_user_id()
            
            # Handle policy document
            if policy_file and policy_file.filename:
                policy_text = extract_text_from_pdf(policy_file)
                save_policy_to_cache(policy_text, user_id)
            else:
                # Try to load cached policy
                policy_text = get_cached_policy(user_id)
                if not policy_text:
                    return render_template('index.html', error="No policy document available. Please upload one.")
                logger.debug("Using cached policy document")
            
            submission_text = extract_text_from_pdf(submission_file)
            
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

