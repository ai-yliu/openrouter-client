#!/usr/bin/env python3
"""
Example usage of the OpenRouter API client as a Python package.

This script demonstrates how to use the OpenRouter API client programmatically.
"""

import os
import sys
from openrouter.config_handler import load_config
from openrouter.api_client import process_text, process_image, process_pdf
from openrouter.utils import determine_input_type, format_response

def main():
    """Example usage of the OpenRouter API client."""
    
    # Check command line arguments
    if len(sys.argv) < 2:
        print("Usage: python example_usage.py <input_file>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    config_file = os.path.join(os.path.dirname(__file__), "example_config.ini")
    
    # Validate input file exists for local files
    if not input_file.startswith(('http://', 'https://')) and not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' does not exist")
        sys.exit(1)
    
    # Validate config file exists
    if not os.path.exists(config_file):
        print(f"Error: Configuration file '{config_file}' does not exist")
        sys.exit(1)
    
    # Load configuration
    config = load_config(config_file)
    
    # Determine input type
    input_type = determine_input_type(input_file)
    print(f"Detected input type: {input_type}")
    
    # Process the input file based on its type
    if input_type == "image":
        print(f"Processing image: {input_file}")
        response = process_image(input_file, config)
    elif input_type == "pdf":
        print(f"Processing PDF: {input_file}")
        response = process_pdf(input_file, config)
    else:  # text
        print(f"Processing text file: {input_file}")
        response = process_text(input_file, config)
    
    # Format and print the response
    formatted_output = format_response(response)
    print(formatted_output)

if __name__ == "__main__":
    main()
