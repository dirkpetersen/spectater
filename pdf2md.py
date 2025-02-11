#!/usr/bin/env python3

import argparse
import os
import pathlib
import sys
from pathlib import Path
import shutil

# Reuse existing PDF processing from app.py
from app import extract_text_from_file

class MockFile:
    """Simulates Flask FileStorage for CLI file inputs (from testpdf.py)"""
    def __init__(self, filepath):
        self.filename = os.path.basename(filepath)
        self.filepath = filepath
        
    def save(self, destination):
        """Copy file to destination path for processing"""
        shutil.copyfile(self.filepath, destination)

def convert_pdf_to_markdown(pdf_path: str, md_path: str) -> None:
    """Convert PDF file to markdown using existing app logic"""
    try:
        # Validate input file
        if not os.path.isfile(pdf_path):
            raise FileNotFoundError(f"Input file not found: {pdf_path}")
            
        # Process PDF using existing app functionality
        mock_file = MockFile(pdf_path)
        markdown_text = extract_text_from_file(mock_file)
        
        # Ensure output directory exists
        Path(md_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Write markdown output
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(markdown_text)
            
        print(f"Successfully converted:\n  {pdf_path}\n  -> {md_path}")
        
    except Exception as e:
        raise RuntimeError(f"Conversion failed: {str(e)}") from e

def main():
    parser = argparse.ArgumentParser(
        description='Convert PDF documents to structured markdown',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    
    parser.add_argument('input_pdf', 
                       help='Input PDF file path')
    parser.add_argument('output_md', 
                       nargs='?',
                       help='Output markdown file path (optional)')
    
    args = parser.parse_args()
    
    # Generate output filename if not specified
    if args.output_md:
        md_path = args.output_md
    else:
        input_path = Path(args.input_pdf)
        # Create output path in same directory as input PDF
        md_path = str(input_path.with_suffix('.md'))
        # Handle case where original file had no extension
        if md_path == str(input_path):
            md_path = str(input_path.parent / f"{input_path.stem}.md")

    try:
        convert_pdf_to_markdown(args.input_pdf, md_path)
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
