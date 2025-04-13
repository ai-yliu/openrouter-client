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
import db_logger # Import the new module
import base64 # For encoding image/pdf input
import json # For parsing JSON output from NER steps
# Need config loader and input type detector from other modules
try:
    from config_handler import load_config
    from utils import determine_input_type
except ImportError:
    # Fallback if running script directly without package install
    print("Warning: Running compare_llms.py directly. Assuming config_handler.py and utils.py are in the same directory.", file=sys.stderr)
    from config_handler import load_config
    from utils import determine_input_type

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
    parser.add_argument("--db-config", default="db_config.ini", help="Path to the database configuration file.") # Added DB config arg

    args = parser.parse_args()

    # --- Initial Validations ---
    # Validate input file/URL (basic check for local files)
    if not args.input.startswith(('http://', 'https://')) and not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' does not exist.", file=sys.stderr)
        sys.exit(1)

    # Validate config files exist
    config_files_to_check = [args.vlm_config, args.ner_config1, args.ner_config2, args.db_config]
    for config_path in config_files_to_check:
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
        print(f"DB Config: {args.db_config}") # Added DB config path
        print(f"Final Output Path: {final_output_path}")
        print(f"Temporary Directory: {temp_directory}")
        print(f"Debug Mode: {args.debug}")
        print(f"---------------------\n")

    # --- Workflow Implementation ---
    print("Starting LLM comparison workflow...")
    python_executable = sys.executable # Use the same python that's running this script

    # --- Database Setup ---
    conn = db_logger.connect_db(args.db_config)
    if conn is None:
        print("Exiting due to database connection failure.", file=sys.stderr)
        sys.exit(1)

    job_id = None # Initialize job_id
    try:
        # Create Job Record
        job_id = db_logger.create_job(conn, 'compare_llms', args.input)
        if job_id is None:
            raise Exception("Failed to create job record in database.") # Or handle more gracefully

        # --- Workflow Steps ---

        # Step 1: VLM Text Extraction
        task1_id = None # Initialize task ID
        print("\nStep 1: Extracting text using VLM...")
        task1_id = db_logger.create_task(conn, job_id, 1, 'vlm_extraction')
        if task1_id is None: raise Exception("Failed to create VLM task record.")
        # Log VLM input details
        try:
            vlm_config_data = load_config(args.vlm_config)
            input_type = determine_input_type(args.input)
            input_content = args.input # Default for URL or text
            input_content_type = 'url' if args.input.startswith(('http://', 'https://')) else 'text' # Initial guess

            if input_type == 'image' and not args.input.startswith(('http://', 'https://')):
                 input_content_type = 'image_base64'
                 with open(args.input, 'rb') as f:
                     input_content = base64.b64encode(f.read()).decode('utf-8')
            elif input_type == 'pdf' and not args.input.startswith(('http://', 'https://')):
                 input_content_type = 'pdf_base64'
                 # Note: We might not want to log the *entire* base64 PDF content due to size.
                 # Consider logging only metadata or a truncated version, or skipping content logging for PDFs.
                 # For now, logging path as content placeholder for large files.
                 # input_content = base64.b64encode(open(args.input, 'rb').read()).decode('utf-8')
                 input_content = f"local_pdf_path:{args.input}" # Placeholder
            elif input_type == 'text' and not args.input.startswith(('http://', 'https://')):
                 input_content_type = 'text'
                 with open(args.input, 'r', encoding='utf-8') as f:
                     input_content = f.read() # Log actual text content

            vlm_details = {
                'input_source': args.input,
                'input_content_type': input_content_type,
                'input_content': input_content, # Be mindful of size for base64
                'api_request_model': vlm_config_data.get('MODEL'),
                'api_request_system_prompt': vlm_config_data.get('SYSTEM_PROMPT'),
                'api_request_user_prompt': vlm_config_data.get('USER_PROMPT'),
                'api_request_temperature': float(vlm_config_data.get('TEMPERATURE', 0.7)),
                'api_request_top_p': float(vlm_config_data.get('TOP_P', 1.0)),
                'api_request_stream': vlm_config_data.get('STREAM', 'false').lower() == 'true',
                'api_request_response_format': json.loads(vlm_config_data['RESPONSE_FORMAT']) if vlm_config_data.get('RESPONSE_FORMAT', '').startswith('{') else {'type': vlm_config_data.get('RESPONSE_FORMAT', 'text')},
                'api_request_provider_options': json.loads(vlm_config_data['PROVIDER']) if vlm_config_data.get('PROVIDER', '').startswith('{') else None
            }
            db_logger.log_vlm_details(conn, task1_id, vlm_details)
        except Exception as log_err:
            print(f"Warning: Failed to log VLM input details for task {task1_id}: {log_err}", file=sys.stderr)
            # Continue workflow even if logging fails? Or handle more strictly?

        db_logger.update_task_status(conn, task1_id, 'running')
        db_logger.update_job_status(conn, job_id, 'in-progress') # Update job status once first task starts

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
            vlm_result = subprocess.run(vlm_command, check=True, capture_output=True, text=True)
            print(f"  VLM output saved to: {temp_vlm_output_path}")
            # Log VLM output details
            try:
                with open(temp_vlm_output_path, 'r', encoding='utf-8') as f:
                    vlm_output_text_result = f.read()
                # Assuming api_response_id is not directly available from openrouter_client output file for now
                db_logger.update_task_details_output(conn, task1_id, 'vlm_extraction', {'output_text': vlm_output_text_result}, api_response_id=None)
            except Exception as read_err:
                 print(f"Warning: Could not read VLM output file {temp_vlm_output_path} for logging output details: {read_err}", file=sys.stderr)
            db_logger.update_task_status(conn, task1_id, 'completed')
        except subprocess.CalledProcessError as e:
            error_msg = f"Command: {' '.join(e.cmd)}\nStderr: {e.stderr}"
            print(f"  Error during VLM step:\n{error_msg}", file=sys.stderr)
            if task1_id: db_logger.update_task_status(conn, task1_id, 'failed', error_msg)
            if job_id: db_logger.update_job_status(conn, job_id, 'failed', f"VLM step failed: {error_msg}")
            raise # Re-raise to stop workflow and trigger finally


        # Step 2a: NER Run 1
        # Step 2a: NER Run 1
        task2_id = None
        print("\nStep 2a: Running NER with Config 1...")
        task2_id = db_logger.create_task(conn, job_id, 2, 'ner_processing')
        if task2_id is None: raise Exception("Failed to create NER1 task record.")
        # Log NER1 input details
        try:
            ner1_config_data = load_config(args.ner_config1)
            # Read the extracted text from the VLM output file
            vlm_output_text = ""
            try:
                with open(temp_vlm_output_path, 'r', encoding='utf-8') as f:
                    vlm_output_text = f.read()
            except Exception as read_err:
                 print(f"Warning: Could not read VLM output file {temp_vlm_output_path} for NER1 logging: {read_err}", file=sys.stderr)
                 # Decide if this is critical - perhaps raise?

            ner1_details = {
                'input_text': vlm_output_text,
                'api_request_model': ner1_config_data.get('MODEL'),
                'api_request_system_prompt': ner1_config_data.get('SYSTEM_PROMPT'),
                'api_request_user_prompt': ner1_config_data.get('USER_PROMPT'),
                'api_request_temperature': float(ner1_config_data.get('TEMPERATURE', 0.7)),
                'api_request_top_p': float(ner1_config_data.get('TOP_P', 1.0)),
                'api_request_stream': ner1_config_data.get('STREAM', 'false').lower() == 'true',
                'api_request_response_format': json.loads(ner1_config_data['RESPONSE_FORMAT']) if ner1_config_data.get('RESPONSE_FORMAT', '').startswith('{') else {'type': ner1_config_data.get('RESPONSE_FORMAT', 'text')},
                'api_request_provider_options': json.loads(ner1_config_data['PROVIDER']) if ner1_config_data.get('PROVIDER', '').startswith('{') else None
            }
            db_logger.log_ner_details(conn, task2_id, ner1_details)
        except Exception as log_err:
            print(f"Warning: Failed to log NER1 input details for task {task2_id}: {log_err}", file=sys.stderr)

        db_logger.update_task_status(conn, task2_id, 'running')
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
            ner1_result = subprocess.run(ner1_command, check=True, capture_output=True, text=True)
            print(f"  NER1 output saved to: {temp_ner1_output_path}")
            # Log NER1 output details
            try:
                with open(temp_ner1_output_path, 'r', encoding='utf-8') as f:
                    ner1_output_json_result = json.load(f) # Load JSON data
                # Assuming api_response_id is not directly available
                db_logger.update_task_details_output(conn, task2_id, 'ner_processing', {'output_json': ner1_output_json_result}, api_response_id=None)
            except json.JSONDecodeError as json_err:
                 print(f"Warning: Could not parse NER1 output file {temp_ner1_output_path} as JSON for logging: {json_err}", file=sys.stderr)
            except Exception as read_err:
                 print(f"Warning: Could not read NER1 output file {temp_ner1_output_path} for logging output details: {read_err}", file=sys.stderr)
            db_logger.update_task_status(conn, task2_id, 'completed')
        except subprocess.CalledProcessError as e:
            error_msg = f"Command: {' '.join(e.cmd)}\nStderr: {e.stderr}"
            print(f"  Error during NER1 step:\n{error_msg}", file=sys.stderr)
            if task2_id: db_logger.update_task_status(conn, task2_id, 'failed', error_msg)
            if job_id: db_logger.update_job_status(conn, job_id, 'failed', f"NER1 step failed: {error_msg}")
            raise

        # Step 2b: NER Run 2
        # Step 2b: NER Run 2
        task3_id = None
        print("\nStep 2b: Running NER with Config 2...")
        task3_id = db_logger.create_task(conn, job_id, 3, 'ner_processing')
        if task3_id is None: raise Exception("Failed to create NER2 task record.")
        # Log NER2 input details
        try:
            ner2_config_data = load_config(args.ner_config2)
             # Read the extracted text from the VLM output file (again, could optimize)
            vlm_output_text_ner2 = ""
            try:
                # Re-read in case something went wrong before, or could pass vlm_output_text variable
                with open(temp_vlm_output_path, 'r', encoding='utf-8') as f:
                    vlm_output_text_ner2 = f.read()
            except Exception as read_err:
                 print(f"Warning: Could not read VLM output file {temp_vlm_output_path} for NER2 logging: {read_err}", file=sys.stderr)

            ner2_details = {
                'input_text': vlm_output_text_ner2,
                'api_request_model': ner2_config_data.get('MODEL'),
                'api_request_system_prompt': ner2_config_data.get('SYSTEM_PROMPT'),
                'api_request_user_prompt': ner2_config_data.get('USER_PROMPT'),
                'api_request_temperature': float(ner2_config_data.get('TEMPERATURE', 0.7)),
                'api_request_top_p': float(ner2_config_data.get('TOP_P', 1.0)),
                'api_request_stream': ner2_config_data.get('STREAM', 'false').lower() == 'true',
                'api_request_response_format': json.loads(ner2_config_data['RESPONSE_FORMAT']) if ner2_config_data.get('RESPONSE_FORMAT', '').startswith('{') else {'type': ner2_config_data.get('RESPONSE_FORMAT', 'text')},
                'api_request_provider_options': json.loads(ner2_config_data['PROVIDER']) if ner2_config_data.get('PROVIDER', '').startswith('{') else None
            }
            db_logger.log_ner_details(conn, task3_id, ner2_details)
        except Exception as log_err:
            print(f"Warning: Failed to log NER2 input details for task {task3_id}: {log_err}", file=sys.stderr)

        db_logger.update_task_status(conn, task3_id, 'running')
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
            ner2_result = subprocess.run(ner2_command, check=True, capture_output=True, text=True)
            print(f"  NER2 output saved to: {temp_ner2_output_path}")
            # Log NER2 output details
            try:
                with open(temp_ner2_output_path, 'r', encoding='utf-8') as f:
                    ner2_output_json_result = json.load(f) # Load JSON data
                # Assuming api_response_id is not directly available
                db_logger.update_task_details_output(conn, task3_id, 'ner_processing', {'output_json': ner2_output_json_result}, api_response_id=None)
            except json.JSONDecodeError as json_err:
                 print(f"Warning: Could not parse NER2 output file {temp_ner2_output_path} as JSON for logging: {json_err}", file=sys.stderr)
            except Exception as read_err:
                 print(f"Warning: Could not read NER2 output file {temp_ner2_output_path} for logging output details: {read_err}", file=sys.stderr)
            db_logger.update_task_status(conn, task3_id, 'completed')
        except subprocess.CalledProcessError as e:
            error_msg = f"Command: {' '.join(e.cmd)}\nStderr: {e.stderr}"
            print(f"  Error during NER2 step:\n{error_msg}", file=sys.stderr)
            if task3_id: db_logger.update_task_status(conn, task3_id, 'failed', error_msg)
            if job_id: db_logger.update_job_status(conn, job_id, 'failed', f"NER2 step failed: {error_msg}")
            raise

        # Step 3: Comparison
        # Step 3: Comparison
        task4_id = None
        print("\nStep 3: Comparing NER results...")
        task4_id = db_logger.create_task(conn, job_id, 4, 'json_comparison')
        if task4_id is None: raise Exception("Failed to create Comparison task record.")
        # Log Comparison input details
        try:
            comparison_details = {
                'input_json_path1': temp_ner1_output_path,
                'input_json_path2': temp_ner2_output_path
            }
            db_logger.log_comparison_details(conn, task4_id, comparison_details)
        except Exception as log_err:
             print(f"Warning: Failed to log Comparison input details for task {task4_id}: {log_err}", file=sys.stderr)

        db_logger.update_task_status(conn, task4_id, 'running')
        compare_command = [
            python_executable, "-m", "json_comparator",
            temp_ner1_output_path, # Positional argument 1
            temp_ner2_output_path, # Positional argument 2
            "--output", final_output_path # Optional output argument
        ]
        if args.debug: print(f"  Running Comparison command: {' '.join(compare_command)}")
        try:
            compare_result = subprocess.run(compare_command, check=True, capture_output=True, text=True)
            print(f"  Comparison results saved to: {final_output_path}")
            # Log Comparison output details
            try:
                # Read the final comparison output file
                with open(final_output_path, 'r', encoding='utf-8') as f:
                    comparison_output_json_result = json.load(f)
                db_logger.update_task_details_output(conn, task4_id, 'json_comparison', {'output_comparison_json': comparison_output_json_result})
            except json.JSONDecodeError as json_err:
                 print(f"Warning: Could not parse Comparison output file {final_output_path} as JSON for logging: {json_err}", file=sys.stderr)
            except Exception as read_err:
                 print(f"Warning: Could not read Comparison output file {final_output_path} for logging output details: {read_err}", file=sys.stderr)
            db_logger.update_task_status(conn, task4_id, 'completed')
        except subprocess.CalledProcessError as e:
            error_msg = f"Command: {' '.join(e.cmd)}\nStderr: {e.stderr}"
            print(f"  Error during Comparison step:\n{error_msg}", file=sys.stderr)
            if task4_id: db_logger.update_task_status(conn, task4_id, 'failed', error_msg)
            if job_id: db_logger.update_job_status(conn, job_id, 'failed', f"Comparison step failed: {error_msg}")
            raise

        # If we reach here, all steps succeeded
        if job_id: db_logger.update_job_status(conn, job_id, 'completed')
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
            if temp_files: # Only print header if there are files
                 print("Temporary files:")
                 for f in temp_files: print(f"  - {f}")

        # Close database connection
        if 'conn' in locals() and conn is not None:
            db_logger.close_db(conn)


if __name__ == "__main__":
    main()