#!/usr/bin/env python3
"""
OpenRouter API Client

A command-line tool to process text and image files through the OpenRouter API.

Usage:
    python openrouter_client.py --input <input_file> --config <config_file> [--output <output_file>]
"""

import argparse
import os
import sys
# Handle both package import and direct script execution
try:
    from openrouter.config_handler import load_config
    from openrouter.api_client import process_text, process_image, process_pdf
    from openrouter.utils import determine_input_type, generate_default_output_filename, format_response
except ImportError:
    from config_handler import load_config
    from api_client import process_text, process_image, process_pdf
    from utils import determine_input_type, generate_default_output_filename, format_response

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Process files through the OpenRouter API")
    parser.add_argument("--input", required=True, help="Path to input file (image, PDF, or text)")
    parser.add_argument("--config", required=True, help="Path to configuration file")
    parser.add_argument("--output", help="Path to output file (optional)")
    parser.add_argument("--debug", help="Include prompts in output file (Y/N)", default="N")
    args = parser.parse_args()
    
    # Validate input file exists for local files
    if not args.input.startswith(('http://', 'https://')) and not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' does not exist")
        sys.exit(1)
    
    # Validate config file exists
    if not os.path.exists(args.config):
        print(f"Error: Configuration file '{args.config}' does not exist")
        sys.exit(1)
    
    # Load configuration
    config = load_config(args.config)
    
    # Determine input type
    input_type = determine_input_type(args.input)
    
    # Generate default output filename if not provided
    output_file = args.output
    if not output_file:
        output_file = generate_default_output_filename(args.input, config["MODEL"])
    
    # Process the input file based on its type
    if input_type == "image":
        print(f"Processing image: {args.input}")
        response = process_image(args.input, config)
    elif input_type == "pdf":
        print(f"Processing PDF: {args.input}")
        response = process_pdf(args.input, config)
    else:  # text
        print(f"Processing text file: {args.input}")
        response = process_text(args.input, config)
    
    # Format the response for display
    formatted_output = format_response(response)
    
    # Print full formatted output to screen
    print(formatted_output)
    
    # Prepare output based on debug mode
    try:
        if args.debug.upper() == "Y":
            output_content = f"System Prompt:\n{config.get('SYSTEM_PROMPT', '')}\n\n"
            output_content += f"User Prompt:\n{config.get('USER_PROMPT', '')}\n\n"
            output_content += "Response:\n"
            output_content += response["choices"][0]["message"].get("content", "") if "choices" in response else ""
        else:
            output_content = response["choices"][0]["message"].get("content", "") if "choices" in response else formatted_output
    except Exception as e:
        output_content = f"Error: {str(e)}\n\n{formatted_output}"
    
    # Save output to file
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(output_content)
    
    print(f"\nOutput saved to: {output_file}")

if __name__ == "__main__":
    main()
