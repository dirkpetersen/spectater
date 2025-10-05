#!/usr/bin/env python3
"""
CLI tool for testing document evaluation with markdown files
Bypasses PDF extraction for faster debugging
"""

import os
import sys
import argparse
import json
import re
import glob

# Import Flask app components
import app

# Enable debug mode for CLI
app.app.debug = True

# Monkey patch session handling for CLI
class MockSession(dict):
    """Mock Flask session for CLI"""
    def __init__(self):
        super().__init__()
        self['session_id'] = 'cli_user'

    @property
    def permanent(self):
        return True

    @permanent.setter
    def permanent(self, value):
        pass

# Replace session with mock
app.session = MockSession()

def extract_and_parse_json(response: str):
    """Extract and parse JSON from response using same logic as app.py"""
    # Find JSON by counting braces to get complete structure
    json_str = None
    json_match = re.search(r'```(?:json)?\s*\n?(\{[\s\S]*)\s*\n?```', response)
    if json_match:
        json_str = json_match.group(1).strip()
    else:
        start_idx = response.find('{')
        if start_idx != -1:
            brace_count = 0
            for i in range(start_idx, len(response)):
                if response[i] == '{':
                    brace_count += 1
                elif response[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        json_str = response[start_idx:i+1]
                        break

    if json_str:
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"JSON PARSE ERROR: {e}")
            print(f"Failed JSON string:\n{json_str[:500]}...")
            return None
    return None

def main():
    parser = argparse.ArgumentParser(
        description='Test document evaluation with markdown files (bypasses PDF processing)',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('--requirement', '--spec', required=True,
                       help='Requirements/policy document (TXT/MD file)')
    parser.add_argument('--submission', '--submit', required=True,
                       help='Submission document (TXT/MD file)')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug output with detailed JSON parsing info')

    args = parser.parse_args()

    # Read policy/requirements file (with wildcard support)
    try:
        policy_files = glob.glob(args.requirement)
        if not policy_files:
            print(f"Error: No files found matching: {args.requirement}")
            sys.exit(1)

        policy_text = ""
        for policy_file in policy_files:
            with open(policy_file, 'r', encoding='utf-8') as f:
                policy_text += f.read() + "\n"
        print(f"✓ Loaded requirements from: {', '.join(policy_files)} ({len(policy_text)} chars)")
    except Exception as e:
        print(f"Error reading requirements file: {e}")
        sys.exit(1)

    # Read submission files (with wildcard support)
    try:
        submission_files = glob.glob(args.submission)
        if not submission_files:
            print(f"Error: No files found matching: {args.submission}")
            sys.exit(1)

        print(f"✓ Found {len(submission_files)} submission file(s) to evaluate")
    except Exception as e:
        print(f"Error finding submission files: {e}")
        sys.exit(1)

    # Show configuration once
    if args.debug:
        model_id = os.getenv('MODEL_ID', 'anthropic.claude-3-5-haiku-20241022-v1:0')
        print(f"\nLLM Configuration:")
        print(f"  Model: {model_id}")
        print(f"  Max Tokens: Dynamic (2/3 of input bytes, min 5000)")
        print(f"  Temperature: 0 (hardcoded for consistency)")

    # Run evaluation for each submission file separately
    for idx, submission_file in enumerate(submission_files, 1):
        try:
            with open(submission_file, 'r', encoding='utf-8') as f:
                submission_text = f.read()
        except Exception as e:
            print(f"Error reading {submission_file}: {e}")
            continue

        print("\n" + "=" * 80)
        print(f"EVALUATION {idx}/{len(submission_files)}: {os.path.basename(submission_file)}")
        print("=" * 80)
        print(f"Submission: {submission_file} ({len(submission_text)} chars)\n")

        try:
            result, response = app.evaluate_requirements(policy_text, submission_text)

            print(f"RESULT: {result}")

            if args.debug:
                print("\nRAW LLM OUTPUT:")
                print("-" * 80)
                print(response)
                print("-" * 80 + "\n")

                # Parse JSON using same method as app.py
                json_data = extract_and_parse_json(response)

                if json_data:
                    print("PARSED JSON STRUCTURE:")
                    print("-" * 80)
                    print(json.dumps(json_data, indent=2))
                    print("-" * 80 + "\n")

                    print("SUMMARY:")
                    summary = json_data.get('summary', {})
                    print(f"  Statement: {summary.get('statement', 'N/A')}")
                    print(f"  Total Checks: {summary.get('totalChecks', 0)}")
                    print(f"  Passed: {summary.get('passed', 0)}")
                    print(f"  Failed: {summary.get('failed', 0)}")
                    print()

                    print("REQUIREMENTS BREAKDOWN:")
                    for req in json_data.get('requirements', []):
                        status_icon = "✓ PASS" if req.get('pass') else "✗ FAIL"
                        print(f"  {status_icon}: {req.get('requirement')}")
                        if not req.get('pass') and req.get('notes'):
                            print(f"         {req.get('notes')}")
                    print()
                else:
                    print("WARNING: Could not parse JSON from response\n")
            else:
                print("\nRESPONSE:")
                print(response)
                print()

        except Exception as e:
            print(f"Evaluation failed for {submission_file}: {e}")
            if args.debug:
                import traceback
                traceback.print_exc()
            continue

    print("\n" + "=" * 80)
    print(f"COMPLETED {len(submission_files)} EVALUATION(S)")
    print("=" * 80)

if __name__ == '__main__':
    main()
