#!/usr/bin/env python3
"""
LLM Comparison Tool - Processes files through two different LLM configurations and compares results

Implements the workflow:
1. Extract text using VLM
2. Perform NER using two LLMs 
3. Compare NER results
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(
        description="Compare LLM NER results using different configurations"
    )
    # Required arguments
    parser.add_argument("--input", required=True, help="Input file (image/PDF)")
    parser.add_argument("--vlm-config", required=True, help="VLM config file")
    parser.add_argument("--ner-config1", required=True, help="First NER LLM config") 
    parser.add_argument("--ner-config2", required=True, help="Second NER LLM config")
    
    # Output options (mutually exclusive)
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("--output", help="Output file path")
    output_group.add_argument("--output-path", help="Output directory path")
    
    parser.add_argument("--debug", action='store_true', help="Show debug info")
    
    args = parser.parse_args()

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Step 1: Extract text using VLM
            vlm_output = Path(tmpdir) / "vlm_output.json"
            subprocess.run([
                "openrouter",
                "--input", args.input,
                "--config", args.vlm_config,
                "--output", str(vlm_output)
            ], check=True, capture_output=not args.debug)
            
            # Step 2: Process with first NER LLM
            ner1_output = Path(tmpdir) / "ner1_output.json"
            subprocess.run([
                "openrouter",
                "--input", str(vlm_output),
                "--config", args.ner_config1,
                "--output", str(ner1_output)
            ], check=True, capture_output=not args.debug)
            
            # Step 3: Process with second NER LLM
            ner2_output = Path(tmpdir) / "ner2_output.json"
            subprocess.run([
                "openrouter", 
                "--input", str(vlm_output),
                "--config", args.ner_config2,
                "--output", str(ner2_output)
            ], check=True, capture_output=not args.debug)
            
            # Step 4: Compare results
            if args.output_path:
                from utils import generate_default_output_filename
                output_file = generate_default_output_filename(args.input, "comparison")
                output_path = Path(args.output_path) / output_file
                args.output = str(output_path)
            
            subprocess.run([
                "compare-json",
                str(ner1_output),
                str(ner2_output),
                "--output", args.output or "-"
            ], check=True, capture_output=not args.debug)
            
    except subprocess.CalledProcessError as e:
        print(f"Error in processing pipeline: {e}", file=sys.stderr)
        if args.debug:
            print(f"Command failed: {e.cmd}\nError output:\n{e.stderr.decode()}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
