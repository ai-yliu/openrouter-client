#!/usr/bin/env python3
"""
Compare LLMs Tool

A command-line tool to orchestrate the comparison of NER results from two LLMs
on text extracted from an image or PDF, using existing openrouter_client and
json_comparator components.
"""

import argparse
import os
import sys
import subprocess
import tempfile
import shutil

def generate_comparison_output_filename(input_path):
    """
    Generate a default output filename for the comparison result based on the input file.

    Args:
        input_path (str): Path to the original input file or URL.

    Returns:
        str: Default output filename (e.g., "document_comparison.json").
    """
    # Handle potential URLs by extracting the last part
    if '/' in input_path:
        basename = input_path.split('/')[-1]
    else:
        basename = input_path

    # Remove query parameters or fragments from URLs if present
    basename = basename.split('?')[0].split('#')[0]

    name_without_ext = os.path.splitext(basename)[0]
    # Sanitize filename (optional, basic example)
    safe_name = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in name_without_ext)
    return f"{safe_name}_comparison.json"

def main():
    parser = argparse.ArgumentParser(
        description="Compare NER results from two LLMs on text extracted from an image/PDF.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # Required Arguments
    parser.add_argument("--input", required=True, help="Path or URL to the input image or PDF file.")
    parser.add_argument("--vlm-config", required=True, help="Path to the configuration file for the VLM text extraction step.")
    parser.add_argument("--ner-config1", required=True, help="Path to the configuration file for the first NER LLM.")
    parser.add_argument("--ner-config2", required=True, help="Path to the configuration file for the second NER LLM.")

    # Optional Arguments
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("--output", help="Full path (directory + filename) for the final JSON comparison result file.")
    output_group.add_argument("--output-path", help="Directory path where the final JSON comparison result file should be saved (uses auto-generated filename).")

    parser.add_argument("--temp-dir", help="Directory path to store intermediate files. If not provided, uses the system's default temporary directory.")
    parser.add_argument("--debug", action='store_true', help="If set, keeps intermediate temporary files and enables verbose logging.")

    args = parser.parse_args()

    # --- Initial Validations ---
    # Validate input file/URL (basic check for local files)
    if not args.input.startswith(('http://', 'https://')) and not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' does not exist.", file=sys.stderr)
        sys.exit(1)

    # Validate config files exist
    for config_path in [args.vlm_config, args.ner_config1, args.ner_config2]:
        if not os.path.exists(config_path):
            print(f"Error: Configuration file '{config_path}' does not exist.", file=sys.stderr)
            sys.exit(1)

    # Validate output-path if provided
    if args.output_path and not os.path.isdir(args.output_path):
        print(f"Error: Output path '{args.output_path}' is not a valid directory.", file=sys.stderr)
        sys.exit(1)

    # Validate temp-dir if provided
    if args.temp_dir and not os.path.isdir(args.temp_dir):
        print(f"Error: Temporary directory '{args.temp_dir}' is not a valid directory.", file=sys.stderr)
        sys.exit(1)

    # --- Determine Paths ---
    temp_directory = args.temp_dir if args.temp_dir else tempfile.gettempdir()
    temp_files = [] # To keep track of files for cleanup

    # Determine final output path
    if args.output:
        final_output_path = args.output
        # Ensure output directory exists if specified in --output
        output_dir = os.path.dirname(final_output_path)
        if output_dir and not os.path.exists(output_dir):
             try:
                 os.makedirs(output_dir)
                 if args.debug: print(f"Created output directory: {output_dir}")
             except OSError as e:
                 print(f"Error: Could not create output directory '{output_dir}'. {e}", file=sys.stderr)
                 sys.exit(1)
    elif args.output_path:
        default_filename = generate_comparison_output_filename(args.input)
        final_output_path = os.path.join(args.output_path, default_filename)
    else:
        # Default to current working directory
        default_filename = generate_comparison_output_filename(args.input)
        final_output_path = default_filename

    if args.debug:
        print(f"--- Configuration ---")
        print(f"Input: {args.input}")
        print(f"VLM Config: {args.vlm_config}")
        print(f"NER Config 1: {args.ner_config1}")
        print(f"NER Config 2: {args.ner_config2}")
        print(f"Final Output Path: {final_output_path}")
        print(f"Temporary Directory: {temp_directory}")
        print(f"Debug Mode: {args.debug}")
        print(f"---------------------\n")

    # --- Workflow Implementation ---
    print("Starting LLM comparison workflow...")
    python_executable = sys.executable # Use the same python that's running this script

    try:
        # Step 1: VLM Text Extraction
        print("\nStep 1: Extracting text using VLM...")
        temp_vlm_output_path = os.path.join(temp_directory, f"compare_llms_vlm_{os.path.basename(args.input)}.txt")
        temp_files.append(temp_vlm_output_path)
        vlm_command = [
            python_executable, "-m", "openrouter_client",
            "--input", args.input,
            "--config", args.vlm_config,
            "--output", temp_vlm_output_path
        ]
        if args.debug: print(f"  Running VLM command: {' '.join(vlm_command)}")
        try:
            subprocess.run(vlm_command, check=True, capture_output=True, text=True)
            print(f"  VLM output saved to: {temp_vlm_output_path}")
        except subprocess.CalledProcessError as e:
            print(f"  Error during VLM step (Command: {' '.join(e.cmd)}):\n{e.stderr}", file=sys.stderr)
            raise # Re-raise to trigger finally block and stop workflow


        # Step 2a: NER Run 1
        print("\nStep 2a: Running NER with Config 1...")
        temp_ner1_output_path = os.path.join(temp_directory, f"compare_llms_ner1_{os.path.basename(args.input)}.json")
        temp_files.append(temp_ner1_output_path)
        ner1_command = [
            python_executable, "-m", "openrouter_client",
            "--input", temp_vlm_output_path, # Use VLM output as input
            "--config", args.ner_config1,
            "--output", temp_ner1_output_path
            # Ensure ner-config1 specifies json output format
        ]
        if args.debug: print(f"  Running NER1 command: {' '.join(ner1_command)}")
        try:
            subprocess.run(ner1_command, check=True, capture_output=True, text=True)
            print(f"  NER1 output saved to: {temp_ner1_output_path}")
        except subprocess.CalledProcessError as e:
            print(f"  Error during NER1 step (Command: {' '.join(e.cmd)}):\n{e.stderr}", file=sys.stderr)
            raise

        # Step 2b: NER Run 2
        print("\nStep 2b: Running NER with Config 2...")
        temp_ner2_output_path = os.path.join(temp_directory, f"compare_llms_ner2_{os.path.basename(args.input)}.json")
        temp_files.append(temp_ner2_output_path)
        ner2_command = [
            python_executable, "-m", "openrouter_client",
            "--input", temp_vlm_output_path, # Use VLM output as input
            "--config", args.ner_config2,
            "--output", temp_ner2_output_path
            # Ensure ner-config2 specifies json output format
        ]
        if args.debug: print(f"  Running NER2 command: {' '.join(ner2_command)}")
        try:
            subprocess.run(ner2_command, check=True, capture_output=True, text=True)
            print(f"  NER2 output saved to: {temp_ner2_output_path}")
        except subprocess.CalledProcessError as e:
            print(f"  Error during NER2 step (Command: {' '.join(e.cmd)}):\n{e.stderr}", file=sys.stderr)
            raise

        # Step 3: Comparison
        print("\nStep 3: Comparing NER results...")
        compare_command = [
            python_executable, "-m", "json_comparator",
            temp_ner1_output_path, # Positional argument 1
            temp_ner2_output_path, # Positional argument 2
            "--output", final_output_path # Optional output argument
        ]
        if args.debug: print(f"  Running Comparison command: {' '.join(compare_command)}")
        try:
            subprocess.run(compare_command, check=True, capture_output=True, text=True)
            print(f"  Comparison results saved to: {final_output_path}")
        except subprocess.CalledProcessError as e:
            print(f"  Error during Comparison step (Command: {' '.join(e.cmd)}):\n{e.stderr}", file=sys.stderr)
            raise

        print("\nWorkflow completed successfully.")

    except Exception as e:
        print(f"\nAn error occurred during the workflow: {e}", file=sys.stderr)
        # Exit with error code 1 if an exception occurred during the try block
        sys.exit(1)
    finally:
        # Cleanup temporary files unless in debug mode
        if not args.debug:
            print("\nCleaning up temporary files...")
            for temp_file_path in temp_files:
                try:
                    if os.path.exists(temp_file_path):
                        os.remove(temp_file_path)
                        # print(f"  Removed: {temp_file_path}") # Optional verbose cleanup
                except OSError as e:
                    print(f"  Warning: Could not remove temporary file '{temp_file_path}'. {e}", file=sys.stderr)
        else:
            print("\nDebug mode: Skipping temporary file cleanup.")
            print("Temporary files:")
            for f in temp_files: print(f"  - {f}")


if __name__ == "__main__":
    main()