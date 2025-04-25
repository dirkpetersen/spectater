#!/usr/bin/env python3

import os
import sys
import argparse
import shutil
from pathlib import Path

# Import Flask app components
import app

# Monkey patch user ID handling for CLI
app.get_user_id = lambda: 'cli_user'  # Fixed ID for CLI user

class MockFile:
    """Simulates Flask FileStorage for CLI file inputs"""
    def __init__(self, filepath):
        self.filename = os.path.basename(filepath)
        self.filepath = filepath
        
    def save(self, destination):
        """Copy file to destination path for processing"""
        shutil.copyfile(self.filepath, destination)

def main():
    # Configure CLI arguments
    parser = argparse.ArgumentParser(description='Evaluate PDF submissions against requirements')
    parser.add_argument('--spec', help='Specification document (PDF/TXT/HTML/MD)')
    parser.add_argument('--submit', required=True, 
                       help='Submission document (PDF/TXT/HTML/MD)')
    args = parser.parse_args()

    # Process specification file
    policy_text = ''
    if args.spec:
        spec_file = MockFile(args.spec)
        try:
            app.validate_file_type(spec_file)
            policy_text = app.extract_text_from_file(spec_file)
            app.save_policy_to_cache(policy_text.strip(), app.get_user_id())
        except Exception as e:
            print(f"Error processing policy: {str(e)}")
            sys.exit(1)
    else:
        # Load cached policy
        policy_text = app.get_cached_policy(app.get_user_id())
        if not policy_text:
            print("Error: No cached policy found - provide --spec")
            sys.exit(1)

    # Process submission file
    submit_file = MockFile(args.submit)
    try:
        app.validate_file_type(submit_file)
        submission_text = app.extract_text_from_file(submit_file).strip()
    except Exception as e:
        print(f"Error processing submission: {str(e)}")
        sys.exit(1)

    # Run evaluation and display results
    try:
        result, explanation = app.evaluate_requirements(policy_text, submission_text)
        print(f"\nEVALUATION RESULT: {result}")
        print(f"\nANALYSIS:\n{explanation}\n")
    except Exception as e:
        print(f"Evaluation failed: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
