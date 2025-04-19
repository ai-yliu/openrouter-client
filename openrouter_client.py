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
def run_openrouter_processing(input_path, config_path):
    """
    Processes an input file using OpenRouter based on a configuration file.

    Args:
        input_path (str): Path or URL to the input file (image, PDF, text).
        config_path (str): Path to the configuration file.

    Returns:
        dict: The raw JSON response dictionary from the OpenRouter API,
              or a dictionary containing an 'error' key if processing fails.
    """
    # Basic validation (could be enhanced or assumed valid by caller)
    if not input_path.startswith(('http://', 'https://')) and not os.path.exists(input_path):
        return {"error": f"Input file '{input_path}' does not exist"}
    if not os.path.exists(config_path):
        return {"error": f"Configuration file '{config_path}' does not exist"}

    try:
        # Load configuration
        config = load_config(config_path)

        # Determine input type
        input_type = determine_input_type(input_path)

        # Process the input file based on its type
        print(f"Processing {input_type}: {input_path} with config {config_path}") # Keep some logging
        if input_type == "image":
            response = process_image(input_path, config)
        elif input_type == "pdf":
            response = process_pdf(input_path, config)
        else:  # text
            response = process_text(input_path, config)

        # Return the raw response (could also extract content here if needed)
        return response

    except Exception as e:
        print(f"Error during OpenRouter processing: {e}", file=sys.stderr)
        return {"error": f"Processing failed: {str(e)}"}


def main():
    """CLI Entry point."""
def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Process files through the OpenRouter API")
    parser.add_argument("--input", required=True, help="Path to input file (image, PDF, or text)")
    parser.add_argument("--config", required=True, help="Path to configuration file")
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("--output", help="Complete output file path including filename")
    output_group.add_argument("--output-path", help="Directory path for output (uses auto-generated filename)")
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
    
    # Call the core processing function
    response = run_openrouter_processing(args.input, args.config)

    # Check for errors returned by the processing function
    if response and "error" in response:
        print(f"Error: {response['error']}", file=sys.stderr)
        sys.exit(1)
    elif not response:
        print("Error: Processing failed with no response.", file=sys.stderr)
        sys.exit(1)

    # --- Handle CLI Output ---
    # Load config again just for output formatting (could optimize by returning config from run_ function)
    config = load_config(args.config)

    # Determine output file path for CLI usage
    output_file = None
    if args.output:
        output_file = args.output
    elif args.output_path:
        output_file = os.path.join(args.output_path, generate_default_output_filename(args.input, config.get("MODEL", "unknown_model")))
        # Ensure output directory exists
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
             try:
                 os.makedirs(output_dir)
             except OSError as e:
                 print(f"Error: Could not create output directory '{output_dir}'. {e}", file=sys.stderr)
                 sys.exit(1) # Exit if cannot create dir for output
    else:
        # Default behavior if neither --output nor --output-path is given
         output_file = generate_default_output_filename(args.input, config.get("MODEL", "unknown_model"))
    
    # Format the response for display
    formatted_output = format_response(response)
    
    # Print full formatted output to screen
    print(formatted_output)
    
    # Prepare output based on debug mode
    try:
        if args.debug.upper() == "Y":
            # Need to re-parse the response format from config for logging
            # Import helper from api_client (assuming it's importable)
            try:
                from api_client import _parse_json_config_value
                import json # For formatting the dict as string
                response_format_obj = _parse_json_config_value(config.get("RESPONSE_FORMAT"), default={"type": "text"})
                response_format_str = json.dumps(response_format_obj, indent=2)
            except ImportError:
                 response_format_str = f"[Could not import _parse_json_config_value to parse: {config.get('RESPONSE_FORMAT', 'N/A')}]"
            except Exception as parse_err:
                 response_format_str = f"[Error parsing RESPONSE_FORMAT: {parse_err}]"

            output_content = f"--- DEBUG INFO ---\n"
            output_content += f"System Prompt:\n{config.get('SYSTEM_PROMPT', '[Not Set]')}\n\n"
            output_content += f"User Prompt:\n{config.get('USER_PROMPT', '[Not Set]')}\n\n"
            output_content += f"Response Format:\n{response_format_str}\n\n"
            output_content += f"--- RESPONSE ---\n"
            # Safely access response content
            try:
                output_content += response["choices"][0]["message"].get("content", "[No content found in response]")
            except (KeyError, IndexError, TypeError):
                 output_content += "[Could not extract content from response structure]"
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
