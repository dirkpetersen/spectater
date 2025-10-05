#!/usr/bin/env python3
"""
Extract text from PDF using AWS Textract and convert to Markdown
Best practices: Upload to S3, use async processing, and official parser library
"""

import boto3
import json
import time
from pathlib import Path
from botocore.exceptions import ClientError
from trp import Document


def upload_to_s3(pdf_path: str, bucket_name: str = None) -> tuple:
    """
    Upload PDF to S3 bucket

    Args:
        pdf_path: Path to the PDF file
        bucket_name: S3 bucket name (optional, will use default or create)

    Returns:
        tuple: (bucket_name, object_key)
    """
    s3 = boto3.client('s3')

    # Use provided bucket or create a default name
    if not bucket_name:
        account_id = boto3.client('sts').get_caller_identity()['Account']
        bucket_name = f'textract-documents-{account_id}'

    # Create bucket if it doesn't exist
    try:
        s3.head_bucket(Bucket=bucket_name)
        print(f"Using existing bucket: {bucket_name}")
    except ClientError:
        print(f"Creating bucket: {bucket_name}")
        try:
            # Get current region
            session = boto3.session.Session()
            region = session.region_name or 'us-east-1'

            # us-east-1 doesn't need LocationConstraint
            if region == 'us-east-1':
                s3.create_bucket(Bucket=bucket_name)
            else:
                s3.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': region}
                )
        except ClientError as e:
            if 'BucketAlreadyOwnedByYou' not in str(e):
                raise

    # Upload file
    file_name = Path(pdf_path).name
    object_key = f'documents/{file_name}'

    print(f"Uploading {pdf_path} to s3://{bucket_name}/{object_key}")
    s3.upload_file(pdf_path, bucket_name, object_key)

    return bucket_name, object_key


def start_textract_job(bucket_name: str, object_key: str) -> str:
    """
    Start asynchronous Textract analysis job

    Args:
        bucket_name: S3 bucket name
        object_key: S3 object key

    Returns:
        str: Job ID
    """
    textract = boto3.client('textract')

    print("Starting Textract analysis job...")
    response = textract.start_document_analysis(
        DocumentLocation={
            'S3Object': {
                'Bucket': bucket_name,
                'Name': object_key
            }
        },
        FeatureTypes=['TABLES', 'FORMS', 'LAYOUT']
    )

    job_id = response['JobId']
    print(f"Job started with ID: {job_id}")
    return job_id


def get_textract_results(job_id: str) -> dict:
    """
    Poll for Textract job completion and retrieve results

    Args:
        job_id: Textract job ID

    Returns:
        dict: Complete Textract response with all blocks
    """
    textract = boto3.client('textract')

    print("Waiting for Textract job to complete...")

    # Poll for completion
    while True:
        response = textract.get_document_analysis(JobId=job_id)
        status = response['JobStatus']

        print(f"Job status: {status}")

        if status == 'SUCCEEDED':
            break
        elif status == 'FAILED':
            raise Exception(f"Textract job failed: {response.get('StatusMessage', 'Unknown error')}")

        time.sleep(5)  # Wait 5 seconds before polling again

    # Collect all pages of results
    all_blocks = response['Blocks']
    next_token = response.get('NextToken')

    while next_token:
        print("Fetching additional result pages...")
        response = textract.get_document_analysis(
            JobId=job_id,
            NextToken=next_token
        )
        all_blocks.extend(response['Blocks'])
        next_token = response.get('NextToken')

    print(f"Retrieved {len(all_blocks)} blocks")
    return {'Blocks': all_blocks}


def analyze_pdf_with_textract(pdf_path: str, bucket_name: str = None) -> dict:
    """
    Analyze a PDF file using AWS Textract via S3 (best practice)

    Args:
        pdf_path: Path to the PDF file
        bucket_name: Optional S3 bucket name

    Returns:
        dict: Textract response with all blocks
    """
    # Upload to S3
    bucket, key = upload_to_s3(pdf_path, bucket_name)

    # Start async job
    job_id = start_textract_job(bucket, key)

    # Get results
    results = get_textract_results(job_id)

    return results


def get_table_cell_positions(table):
    """Get set of all text positions covered by table cells"""
    positions = set()
    for row in table.rows:
        for cell in row.cells:
            if hasattr(cell, 'geometry') and cell.geometry:
                bbox = cell.geometry.boundingBox
                # Create a position key from bounding box
                pos_key = (
                    round(bbox.top, 4),
                    round(bbox.left, 4),
                    round(bbox.width, 4),
                    round(bbox.height, 4)
                )
                positions.add(pos_key)
    return positions


def is_line_in_table(line, table_positions):
    """Check if a line overlaps with table cell positions"""
    if not hasattr(line, 'geometry') or not line.geometry:
        return False

    bbox = line.geometry.boundingBox
    line_key = (
        round(bbox.top, 4),
        round(bbox.left, 4),
        round(bbox.width, 4),
        round(bbox.height, 4)
    )

    # Check for overlap with any table cell
    for table_pos in table_positions:
        t_top, t_left, t_width, t_height = table_pos
        l_top, l_left, l_width, l_height = line_key

        # Check if line is within table bounds
        if (t_top <= l_top <= t_top + t_height and
            t_left <= l_left <= t_left + t_width):
            return True

    return False


def format_cell_content(cell_text: str, preserve_structure: bool = True) -> str:
    """
    Format cell content to preserve internal structure like key-value pairs.
    Works for any document with complex cells (invoices, forms, reports, etc.)

    Args:
        cell_text: Raw cell text
        preserve_structure: Whether to preserve line breaks and structure

    Returns:
        str: Formatted cell text
    """
    if not cell_text:
        return ""

    if not preserve_structure:
        # Simple mode: just clean up whitespace
        return " ".join(cell_text.split())

    # Detect if cell contains multiple items (common patterns across documents)
    lines = [line.strip() for line in cell_text.split('\n') if line.strip()]

    if len(lines) <= 1:
        # Single line cell - just return it
        return cell_text.strip()

    # Multi-line cell: preserve structure with <br> tags for markdown compatibility
    # This works for: invoice line items, form fields, nested data, etc.
    formatted = "<br>".join(lines)

    return formatted


def convert_to_markdown(response: dict, preserve_cell_structure: bool = True) -> str:
    """
    Convert Textract response to Markdown using the official amazon-textract-response-parser library.
    This is a GENERAL solution that works for ANY PDF with tables:
    - Invoices, receipts, financial statements
    - Forms (insurance, tax, medical, legal)
    - Reports with complex tables
    - Contracts with nested data

    Args:
        response: Textract API response
        preserve_cell_structure: Keep internal structure of complex cells

    Returns:
        str: Markdown formatted text
    """
    doc = Document(response)
    markdown_content = "# Document Content\n\n"

    # Iterate through pages
    for page_num, page in enumerate(doc.pages, start=1):
        if page_num > 1:
            markdown_content += f"\n---\n\n## Page {page_num}\n\n"

        # Get all table cell positions to exclude those lines from output
        table_positions = set()
        for table in page.tables:
            table_positions.update(get_table_cell_positions(table))

        # Add lines (text content) that are NOT part of tables
        for line in page.lines:
            if not is_line_in_table(line, table_positions):
                markdown_content += line.text + "\n\n"

        # Add tables with proper handling of merged cells and nested content
        for table_idx, table in enumerate(page.tables):
            markdown_content += f"### Table {table_idx + 1}\n\n"
            markdown_table = ""

            for r, row in enumerate(table.rows):
                row_text = "|"
                separator_text = "|"

                for cell in row.cells:
                    # The library handles merged cells and text extraction
                    cell_text = cell.text.strip() if cell.text else ""

                    # Format cell to preserve internal structure (works for any document type)
                    cell_text = format_cell_content(cell_text, preserve_cell_structure)

                    # Escape pipe characters in cell content
                    cell_text = cell_text.replace("|", "\\|")

                    row_text += f" {cell_text} |"
                    separator_text += " --- |"

                markdown_table += row_text + "\n"

                # Add separator after first row (header)
                if r == 0:
                    markdown_table += separator_text + "\n"

            markdown_content += markdown_table + "\n\n"

    return markdown_content


def main():
    import sys
    import argparse

    parser = argparse.ArgumentParser(
        description='Convert any PDF with tables to Markdown using AWS Textract',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python textract_to_markdown.py invoice.pdf
  python textract_to_markdown.py contract.pdf --bucket my-bucket
  python textract_to_markdown.py form.pdf --no-structure

Supported document types:
  - Insurance certificates, ACORD forms
  - Invoices, receipts, financial statements
  - Tax forms, government forms
  - Contracts with tables
  - Medical records, lab results
  - Research papers, reports
  - Any PDF with structured tables
        """
    )
    parser.add_argument('pdf_path', help='Path to PDF file')
    parser.add_argument('--bucket', help='S3 bucket name (optional, will create if needed)')
    parser.add_argument('--output', help='Output markdown file path (default: input_textract.md)')
    parser.add_argument('--no-structure', action='store_true',
                       help='Flatten multi-line cells instead of preserving structure')

    args = parser.parse_args()

    pdf_path = args.pdf_path
    bucket_name = args.bucket
    output_path = args.output or pdf_path.replace('.pdf', '_textract.md')

    if not pdf_path.lower().endswith('.pdf'):
        print("Error: Input file must be a PDF")
        sys.exit(1)

    print(f"Analyzing PDF: {pdf_path}")

    # Analyze with Textract
    try:
        response = analyze_pdf_with_textract(pdf_path, bucket_name)
    except Exception as e:
        print(f"Error analyzing PDF: {e}")
        sys.exit(1)

    # Save raw response for debugging
    json_path = output_path.replace('.md', '_response.json')
    with open(json_path, 'w') as f:
        json.dump(response, f, indent=2)
    print(f"Saved raw response to: {json_path}")

    # Count tables found
    table_count = sum(1 for block in response['Blocks'] if block.get('BlockType') == 'TABLE')
    print(f"Found {table_count} table(s) in the document")

    # Count other block types
    block_types = {}
    for block in response['Blocks']:
        block_type = block.get('BlockType', 'UNKNOWN')
        block_types[block_type] = block_types.get(block_type, 0) + 1

    print("\nBlock type summary:")
    for btype, count in sorted(block_types.items()):
        print(f"  {btype}: {count}")

    # Convert to markdown using official parser library
    print("\nConverting to Markdown using amazon-textract-response-parser...")
    preserve_structure = not args.no_structure
    markdown_content = convert_to_markdown(response, preserve_structure)

    # Save markdown
    with open(output_path, 'w') as f:
        f.write(markdown_content)

    print(f"\n✓ Saved markdown to: {output_path}")
    print("\nRequired library: pip install amazon-textract-response-parser boto3")


if __name__ == '__main__':
    main()
