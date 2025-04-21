"""
Flask Web Application for LLM Comparison GUI
"""

from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import sys
import uuid
import threading # Using threading for simple background tasks initially

import db_logger
import psycopg2
import json # Import json at the top level
from dotenv import load_dotenv # Import dotenv
from config_handler import load_config
from utils import determine_input_type

load_dotenv() # Load variables from .env file into environment

# --- Flask App Setup ---
app = Flask(__name__)
# Get UPLOAD_FOLDER from environment variable or use default
# Use path relative to the current working directory where the app is RUN
upload_folder_path = os.getenv('UPLOAD_FOLDER', 'uploads') # Default to 'uploads'
app.config['UPLOAD_FOLDER'] = os.path.abspath(upload_folder_path) # Ensure it's absolute based on CWD
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # Limit upload size (e.g., 16MB)

# Ensure upload folder exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# --- Background Task Management (Simple Example) ---
# WARNING: This simple threading approach is not robust for production.
# Consider Celery or Flask-Executor for better task management.
active_jobs = {} # Dictionary to track background job threads {job_id: thread_object}

def run_comparison_workflow(job_id, input_file_path, vlm_config_path, ner_config1_path, ner_config2_path, db_config_path):
    """The actual workflow logic run in a background thread."""
    print(f"Starting background workflow for job: {job_id}")
    import time
    import openrouter_client # Import within thread if needed
    import db_logger # Import within thread if needed
    import json_comparator # Import within thread if needed
    import configparser # Import needed for temp config writing

    # Connect to DB
    conn = db_logger.connect_db(db_config_path)
    if conn is None:
        print(f"Error: Could not connect to database in background workflow for job {job_id}", file=sys.stderr)
        return

    task1_id = None
    task2_id = None
    task3_id = None
    task4_id = None
    task5_id = None # Added for Task 5
    temp_vlm_txt = None
    temp_review_config_path = None # Added for Task 5 cleanup
    vlm_response = None
    ner1_response = None
    ner2_response = None
    ner1_content = None
    ner2_content = None
    comparison_result = None
    review_response = None

    try: # Main workflow try block
        # Step 1: VLM Extraction
        task1_id = db_logger.create_task(conn, job_id, 1, 'vlm_extraction')
        if task1_id is None: raise Exception("Failed to create VLM task record.")
        print(f"DEBUG: Entering VLM details logging for task {task1_id}")
        try:
            vlm_config_data = load_config(vlm_config_path)
            input_type = determine_input_type(input_file_path)
            input_content = input_file_path
            input_content_type = 'url' if input_file_path.startswith(('http://', 'https://')) else 'text'
            if input_type == 'image' and not input_file_path.startswith(('http://', 'https://')):
                input_content_type = 'image_base64'
                with open(input_file_path, 'rb') as f:
                    import base64
                    input_content = base64.b64encode(f.read()).decode('utf-8')
            elif input_type == 'pdf' and not input_file_path.startswith(('http://', 'https://')):
                input_content_type = 'pdf_base64'
                input_content = f"local_pdf_path:{input_file_path}"
            elif input_type == 'text' and not input_file_path.startswith(('http://', 'https://')):
                input_content_type = 'text'
                with open(input_file_path, 'r', encoding='utf-8') as f:
                    input_content = f.read()
            vlm_details = {
                'input_source': input_file_path, 'input_content_type': input_content_type, 'input_content': input_content,
                'api_request_model': vlm_config_data.get('MODEL'), 'api_request_system_prompt': vlm_config_data.get('SYSTEM_PROMPT'),
                'api_request_user_prompt': vlm_config_data.get('USER_PROMPT'), 'api_request_temperature': float(vlm_config_data.get('TEMPERATURE', 0.7)),
                'api_request_top_p': float(vlm_config_data.get('TOP_P', 1.0)), 'api_request_stream': vlm_config_data.get('STREAM', 'false').lower() == 'true',
                'api_request_response_format': json.loads(vlm_config_data['RESPONSE_FORMAT']) if vlm_config_data.get('RESPONSE_FORMAT', '').startswith('{') else {'type': vlm_config_data.get('RESPONSE_FORMAT', 'text')},
                'api_request_provider_options': json.loads(vlm_config_data['PROVIDER']) if vlm_config_data.get('PROVIDER', '').startswith('{') else None
            }
            db_logger.log_vlm_details(conn, task1_id, vlm_details)
        except Exception as log_err:
            print(f"Warning: Failed to log VLM input details for task {task1_id}: {log_err}", file=sys.stderr)
        print(f"DEBUG: Finished VLM details logging for task {task1_id}")
        db_logger.update_task_status(conn, task1_id, 'running')
        vlm_response = openrouter_client.run_openrouter_processing(input_file_path, vlm_config_path)
        if "error" in vlm_response:
            error_details = vlm_response["error"]; error_message_str = str(error_details) if error_details is not None else "Unknown VLM error"
            db_logger.update_task_status(conn, task1_id, 'failed', error_message_str); db_logger.update_job_status(conn, job_id, 'failed', f"VLM step failed: {error_message_str}")
            return
        db_logger.update_task_details_output(conn, task1_id, 'vlm_extraction', {'output_text': vlm_response.get("choices", [{}])[0].get("message", {}).get("content", "")})
        db_logger.update_task_status(conn, task1_id, 'completed')

        # Step 2: NER 1
        task2_id = db_logger.create_task(conn, job_id, 2, 'ner_processing')
        if task2_id is None: raise Exception("Failed to create NER1 task record.")
        vlm_text = vlm_response.get("choices", [{}])[0].get("message", {}).get("content", "")
        try:
            ner1_config_data = load_config(ner_config1_path)
            ner1_details = {
                'input_text': vlm_text, 'api_request_model': ner1_config_data.get('MODEL'),
                'api_request_system_prompt': ner1_config_data.get('SYSTEM_PROMPT'), 'api_request_user_prompt': ner1_config_data.get('USER_PROMPT'),
                'api_request_temperature': float(ner1_config_data.get('TEMPERATURE', 0.7)), 'api_request_top_p': float(ner1_config_data.get('TOP_P', 1.0)),
                'api_request_stream': ner1_config_data.get('STREAM', 'false').lower() == 'true',
                'api_request_response_format': json.loads(ner1_config_data['RESPONSE_FORMAT']) if ner1_config_data.get('RESPONSE_FORMAT', '').startswith('{') else {'type': ner1_config_data.get('RESPONSE_FORMAT', 'text')},
                'api_request_provider_options': json.loads(ner1_config_data['PROVIDER']) if ner1_config_data.get('PROVIDER', '').startswith('{') else None
            }
            db_logger.log_ner_details(conn, task2_id, ner1_details)
        except Exception as log_err:
            print(f"Warning: Failed to log NER1 input details for task {task2_id}: {log_err}", file=sys.stderr)
        db_logger.update_task_status(conn, task2_id, 'running')
        temp_vlm_txt = input_file_path + ".vlm.txt"
        with open(temp_vlm_txt, "w", encoding="utf-8") as f: f.write(vlm_text or "")
        ner1_response = openrouter_client.run_openrouter_processing(temp_vlm_txt, ner_config1_path)
        if "error" in ner1_response:
            error_details = ner1_response["error"]; error_message_str = str(error_details) if error_details is not None else "Unknown NER1 error"
            db_logger.update_task_status(conn, task2_id, 'failed', error_message_str); db_logger.update_job_status(conn, job_id, 'failed', f"NER1 step failed: {error_message_str}")
            return
        db_logger.update_task_details_output(conn, task2_id, 'ner_processing', {'output_json': ner1_response})
        db_logger.update_task_status(conn, task2_id, 'completed')

        # Step 3: NER 2
        task3_id = db_logger.create_task(conn, job_id, 3, 'ner_processing')
        if task3_id is None: raise Exception("Failed to create NER2 task record.")
        try:
            print(f"DEBUG NER2: Attempting to load config: {ner_config2_path}")
            ner2_config_data = load_config(ner_config2_path)
            print(f"DEBUG NER2: Config loaded successfully.")
            print(f"DEBUG NER2: Preparing details dictionary...")
            ner2_details = {
                'input_text': vlm_text, 'api_request_model': ner2_config_data.get('MODEL'),
                'api_request_system_prompt': ner2_config_data.get('SYSTEM_PROMPT'), 'api_request_user_prompt': ner2_config_data.get('USER_PROMPT'),
                'api_request_temperature': float(ner2_config_data.get('TEMPERATURE', 0.7)), 'api_request_top_p': float(ner2_config_data.get('TOP_P', 1.0)),
                'api_request_stream': ner2_config_data.get('STREAM', 'false').lower() == 'true',
                'api_request_response_format': json.loads(ner2_config_data['RESPONSE_FORMAT']) if ner2_config_data.get('RESPONSE_FORMAT', '').startswith('{') else {'type': ner2_config_data.get('RESPONSE_FORMAT', 'text')},
                'api_request_provider_options': json.loads(ner2_config_data['PROVIDER']) if ner2_config_data.get('PROVIDER', '').startswith('{') else None
            }
            print(f"DEBUG NER2: Details dictionary prepared.")
            print(f"DEBUG NER2: Attempting to log details to DB...")
            db_logger.log_ner_details(conn, task3_id, ner2_details)
            print(f"DEBUG NER2: Details logged successfully.")
        except Exception as log_err:
            print(f"Warning: Failed to log NER2 input details for task {task3_id}: {log_err}", file=sys.stderr)
        db_logger.update_task_status(conn, task3_id, 'running')
        print(f"DEBUG: About to call run_openrouter_processing for NER2 (Task {task3_id})")
        print(f"DEBUG: NER2 Input File (temp_vlm_txt): {temp_vlm_txt}")
        print(f"DEBUG: NER2 Config Path: {ner_config2_path}")
        ner2_response = openrouter_client.run_openrouter_processing(temp_vlm_txt, ner_config2_path)
        if "error" in ner2_response:
            error_details = ner2_response["error"]; error_message_str = str(error_details) if error_details is not None else "Unknown NER2 error"
            db_logger.update_task_status(conn, task3_id, 'failed', error_message_str); db_logger.update_job_status(conn, job_id, 'failed', f"NER2 step failed: {error_message_str}")
            return
        db_logger.update_task_details_output(conn, task3_id, 'ner_processing', {'output_json': ner2_response})
        db_logger.update_task_status(conn, task3_id, 'completed')

        # Step 4: JSON Comparison
        task4_id = db_logger.create_task(conn, job_id, 4, 'json_comparison')
        if task4_id is None: raise Exception("Failed to create Comparison task record.")
        temp_ner1_json = input_file_path + ".ner1.json"
        temp_ner2_json = input_file_path + ".ner2.json"
        try:
            comparison_details = {'input_json_path1': temp_ner1_json, 'input_json_path2': temp_ner2_json}
            db_logger.log_comparison_details(conn, task4_id, comparison_details)
        except Exception as log_err:
            print(f"Warning: Failed to log Comparison input details for task {task4_id}: {log_err}", file=sys.stderr)
        db_logger.update_task_status(conn, task4_id, 'running')

        ner1_content = {}
        ner2_content = {}
        try:
            ner1_content = ner1_response.get("choices", [{}])[0].get("message", {}).get("content", {})
            if isinstance(ner1_content, str): ner1_content = json.loads(ner1_content)
        except (json.JSONDecodeError, IndexError, TypeError) as e:
             print(f"Warning: Could not extract/parse NER1 content for comparison: {e}", file=sys.stderr)
             ner1_content = {"error": "Invalid JSON content from NER1"}
        try:
            ner2_content = ner2_response.get("choices", [{}])[0].get("message", {}).get("content", {})
            if isinstance(ner2_content, str): ner2_content = json.loads(ner2_content)
        except (json.JSONDecodeError, IndexError, TypeError) as e:
             print(f"Warning: Could not extract/parse NER2 content for comparison: {e}", file=sys.stderr)
             ner2_content = {"error": "Invalid JSON content from NER2"}

        try: # Main try for Comparison + Review steps
            comparison_result = json_comparator.run_json_comparison(ner1_content, ner2_content)
            db_logger.update_task_details_output(conn, task4_id, 'json_comparison', {'output_comparison_json': comparison_result})
            db_logger.update_task_status(conn, task4_id, 'completed')

            # --- Step 5: VLM Review (New Step) ---
            task5_id = None
            try: # Main try for Task 5
                print(f"Starting Step 5: VLM Review for job {job_id}")
                mismatched_entities = []
                if comparison_result and 'entities' in comparison_result:
                    for entity in comparison_result['entities']:
                        comp_status = entity.get('comparison', '').lower()
                        if comp_status in ['addition', 'omission']:
                             mismatched_entities.append({"entity_name": entity.get("entity_name"), "entity_value": entity.get("entity_value")})

                if not mismatched_entities:
                    print(f"No mismatched entities found for review in job {job_id}. Skipping VLM Review.")
                    db_logger.update_job_status(conn, job_id, 'completed')
                    return

                mismatched_entities_dict = {"entities": mismatched_entities}
                # Create both pretty and compact JSON versions
                mismatched_json_pretty = json.dumps(mismatched_entities_dict, indent=2)  # For debug printing
                mismatched_json_compact = json.dumps(mismatched_entities_dict, separators=(',', ':'))  # For config file
                print(f"DEBUG: Mismatched entities for review:\n{mismatched_json_pretty}")

                task5_id = db_logger.create_task(conn, job_id, 5, 'vlm_review')
                if task5_id is None: raise Exception("Failed to create VLM Review task record.")

                print(f"DEBUG REVIEW: Attempting to load review config...")
                review_config_path = os.getenv('VLM_REVIEW_CONFIG_PATH', './config/vlm_review.ini')
                print(f"DEBUG REVIEW: Config path: {review_config_path}")
                if not os.path.exists(review_config_path): raise FileNotFoundError(f"Review configuration file not found: {review_config_path}")
                review_config_data = load_config(review_config_path)
                print(f"DEBUG REVIEW: Review config loaded.")

                original_prompt = review_config_data.get('USER_PROMPT', '')
                if '{NER_result}' not in original_prompt:
                     print("Warning: '{NER_result}' placeholder not found in VLM_REVIEW_CONFIG_PATH USER_PROMPT. Sending mismatched entities anyway.", file=sys.stderr)
                     modified_prompt = original_prompt + "\n\nMismatched Entities:\n" + mismatched_json_pretty
                else:
                     modified_prompt = original_prompt.replace('{NER_result}', mismatched_json_compact)

                print(f"DEBUG REVIEW: Preparing review details dictionary...")
                review_details = {
                    'input_source': input_file_path, 'api_request_model': review_config_data.get('MODEL'),
                    'api_request_system_prompt': review_config_data.get('SYSTEM_PROMPT'), 'api_request_user_prompt': modified_prompt,
                    'api_request_temperature': float(review_config_data.get('TEMPERATURE', 0.7)), 'api_request_top_p': float(review_config_data.get('TOP_P', 1.0)),
                    'api_request_stream': review_config_data.get('STREAM', 'false').lower() == 'true',
                    'api_request_response_format': json.loads(review_config_data['RESPONSE_FORMAT']) if review_config_data.get('RESPONSE_FORMAT', '').startswith('{') else {'type': review_config_data.get('RESPONSE_FORMAT', 'text')},
                    'api_request_provider_options': json.loads(review_config_data['PROVIDER']) if review_config_data.get('PROVIDER', '').startswith('{') else None
                }
                print(f"DEBUG REVIEW: Review details dictionary prepared.")
                print(f"DEBUG REVIEW: Attempting to log review details to DB...")
                db_logger.log_review_details(conn, task5_id, review_details)
                print(f"DEBUG REVIEW: Review details logged successfully.")

                print(f"DEBUG REVIEW: Attempting to update task status to 'running'...")
                db_logger.update_task_status(conn, task5_id, 'running')
                print(f"DEBUG REVIEW: Task status updated to 'running'.")

                # --- Create temporary config file by replacing placeholder in original ---
                temp_review_config_path = input_file_path + ".review_config.ini"
                try: # Inner try for file writing
                    with open(review_config_path, 'r', encoding='utf-8') as f_orig:
                        original_config_content = f_orig.read()
                    temp_config_content = original_config_content.replace('{NER_result}', mismatched_json_compact)
                    with open(temp_review_config_path, 'w', encoding='utf-8') as f_temp:
                        f_temp.write(temp_config_content)
                    print(f"DEBUG REVIEW: Temporary review config written to {temp_review_config_path}")
                except Exception as config_write_err:
                     print(f"ERROR writing temporary review config file: {config_write_err}", file=sys.stderr)
                     raise config_write_err # Re-raise

                # Call API (Inside Task 5 try, *after* file write try/except)
                review_response = openrouter_client.run_openrouter_processing(input_file_path, temp_review_config_path)

                # Clean up temp config file *after* the API call attempt
                # try: # Keep commented out
                #     if temp_review_config_path and os.path.exists(temp_review_config_path):
                #          os.remove(temp_review_config_path)
                #          print(f"DEBUG REVIEW: Removed temporary review config file: {temp_review_config_path}")
                # except OSError as e_clean_cfg:
                #     print(f"Warning: Could not remove temp review config file: {e_clean_cfg}", file=sys.stderr)
                if temp_review_config_path: # Only print if path was defined
                    print(f"DEBUG REVIEW: Skipping removal of temporary config file for debugging: {temp_review_config_path}")

                # 6. Handle Response (Still inside the main try block for Task 5)
                if "error" in review_response:
                    error_details = review_response["error"]
                    error_message_str = str(error_details) if error_details is not None else "Unknown VLM Review error"
                    db_logger.update_task_status(conn, task5_id, 'failed', error_message_str)
                    db_logger.update_job_status(conn, job_id, 'failed', f"VLM Review step failed: {error_message_str}")
                    return # Stop workflow

                # Log successful output (Still inside the main try block for Task 5)
                db_logger.update_task_details_output(conn, task5_id, 'vlm_review', {'output_review_json': review_response})
                db_logger.update_task_status(conn, task5_id, 'completed')
                print(f"Finished Step 5: VLM Review for job {job_id}")

            except Exception as review_err: # This except corresponds to the main try block for Task 5
                print(f"ERROR: Exception caught during VLM Review step (Task 5): {type(review_err).__name__} - {review_err}", file=sys.stderr)
                error_message_str = str(review_err) if review_err is not None else "Unknown VLM Review step error"
                if task5_id:
                    db_logger.update_task_status(conn, task5_id, 'failed', error_message_str)
                db_logger.update_job_status(conn, job_id, 'failed', f"VLM Review step failed: {error_message_str}")
                return # Stop workflow

            # Mark job as completed ONLY if VLM Review step also succeeded
            db_logger.update_job_status(conn, job_id, 'completed')

        except Exception as comp_err: # This except corresponds to the try block for Comparison (Task 4)
             print(f"Error during comparison logic or logging: {comp_err}", file=sys.stderr)
             error_message_str = str(comp_err) if comp_err is not None else "Unknown comparison error"
             if task4_id: # Check if task4_id exists before updating
                 db_logger.update_task_status(conn, task4_id, 'failed', error_message_str)
             db_logger.update_job_status(conn, job_id, 'failed', f"Comparison step failed: {error_message_str}")
             try:
                 if temp_vlm_txt and os.path.exists(temp_vlm_txt): os.remove(temp_vlm_txt)
             except OSError as e_clean:
                 print(f"Warning: Could not remove temp VLM file during comparison error handling: {e_clean}", file=sys.stderr)
             return # Stop workflow

        print(f"Finished background workflow for job: {job_id}")

    except Exception as e: # This except corresponds to the main try block for the whole workflow
        print(f"Error in background workflow for job {job_id}: {e}", file=sys.stderr)
        error_message_str = str(e) if e is not None else "Unknown workflow error"
        if job_id:
            db_logger.update_job_status(conn, job_id, 'failed', error_message_str)
    finally: # Corresponds to main workflow try
        # Clean up intermediate files (VLM text) if they exist
        # try: # Keep commented out
        #     if temp_vlm_txt and os.path.exists(temp_vlm_txt): os.remove(temp_vlm_txt)
        # except OSError as e_final_clean:
        #      print(f"Warning: Could not remove temp file during final cleanup: {e_final_clean}", file=sys.stderr)
        if temp_vlm_txt: # Only print if path was defined
            print(f"DEBUG: Skipping removal of temp VLM file for debugging: {temp_vlm_txt}")
        # Close database connection
        if conn:
            db_logger.close_db(conn)

# --- Routes ---

@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('index.html')

@app.route('/static/<path:path>')
def send_static(path):
    """Serves static files (CSS, JS)."""
    return send_from_directory('static', path)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serves uploaded files for display (use with caution in production)."""
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        print(f"File not found for serving: {file_path}", file=sys.stderr)
        return "File not found", 404
    print(f"Serving uploaded file: {file_path}")
    import mimetypes
    mime_type, _ = mimetypes.guess_type(file_path)
    absolute_upload_folder = app.config['UPLOAD_FOLDER']
    print(f"DEBUG: Serving file '{filename}' from directory '{absolute_upload_folder}'")
    try:
        return send_from_directory(absolute_upload_folder, filename, mimetype=mime_type)
    except Exception as e:
        print(f"ERROR in send_from_directory: {e}", file=sys.stderr)
        return "Error serving file", 500

@app.route('/api/v1/jobs', methods=['POST'])
def start_job():
    """Handles file upload and starts the comparison workflow."""
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file:
        filename = str(uuid.uuid4()) + "_" + file.filename
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        try:
            file.save(upload_path)
            print(f"File uploaded successfully to: {upload_path}")

            vlm_config = os.getenv('VLM_CONFIG_PATH', './config/vlm_raw.ini')
            ner1_config = os.getenv('NER1_CONFIG_PATH', './config/llm_cat_qwen2.5-72b.ini')
            ner2_config = os.getenv('NER2_CONFIG_PATH', './config/llm_cat_llama-3.3.ini')
            db_config = os.getenv('DB_CONFIG_PATH', './db_config.ini')
            for cfg_path in [vlm_config, ner1_config, ner2_config, db_config]:
                if not os.path.exists(cfg_path):
                    print(f"Error: Configuration file '{cfg_path}' (from env or default) not found.", file=sys.stderr)
                    if os.path.exists(upload_path):
                        try: os.remove(upload_path); print(f"Cleaned up uploaded file: {upload_path}")
                        except OSError as e: print(f"Error cleaning up file {upload_path}: {e}", file=sys.stderr)
                    return jsonify({"error": f"Missing configuration file: {os.path.basename(cfg_path)}"}), 500

            conn = db_logger.connect_db(db_config)
            if conn is None:
                print("Error: Could not connect to database to create job.", file=sys.stderr)
                return jsonify({"error": "Database connection failed"}), 500
            job_id = None
            try:
                job_id = db_logger.create_job(conn, 'compare_llms', upload_path)
                if not job_id:
                    print("Error: Failed to create job record in database.", file=sys.stderr)
                    return jsonify({"error": "Failed to create job record in database"}), 500
                print(f"Initiating job with DB job_id: {job_id}")
            finally:
                if conn: db_logger.close_db(conn)

            if job_id:
                thread = threading.Thread(target=run_comparison_workflow, args=(
                    job_id, upload_path, vlm_config, ner1_config, ner2_config, db_config
                ))
                thread.start()
                active_jobs[job_id] = thread

                return jsonify({
                    "message": "File uploaded and processing started.",
                    "job_id": job_id,
                    "uploaded_filename": filename
                    }), 202
            else:
                 return jsonify({"error": "Job creation failed, cannot start workflow."}), 500

        except Exception as e:
            print(f"Error during file upload or job start: {e}", file=sys.stderr)
            return jsonify({"error": f"Failed to process file: {e}"}), 500

    return jsonify({"error": "File processing failed."}), 400


@app.route('/api/v1/jobs/<job_id>/status', methods=['GET'])
def get_job_status(job_id):
    """Retrieves the status of a job and its tasks from the database."""
    print(f"Request received for job status: {job_id}")
    db_config_path = os.getenv('DB_CONFIG_PATH', './db_config.ini')
    conn = db_logger.connect_db(db_config_path)
    if conn is None: return jsonify({"error": "Database connection failed"}), 500

    try:
        job_details = db_logger.get_job_status(conn, job_id)
        tasks = db_logger.get_tasks_for_job(conn, job_id)
        if not job_details: return jsonify({"error": f"Job {job_id} not found"}), 404
        if job_details.get('start_time'): job_details['start_time'] = job_details['start_time'].isoformat()
        if job_details.get('end_time'): job_details['end_time'] = job_details['end_time'].isoformat()
        for task in tasks:
            if task.get('start_time'): task['start_time'] = task['start_time'].isoformat()
            if task.get('end_time'): task['end_time'] = task['end_time'].isoformat()

        status_data = {
            "job_id": job_id, "job_status": job_details.get("status"),
            "start_time": job_details.get("start_time"), "end_time": job_details.get("end_time"),
            "error_message": job_details.get("error_message"), "input_source": job_details.get("input_source"),
            "workflow_name": job_details.get("workflow_name"), "tasks": tasks
        }
        return jsonify(status_data)
    finally:
        db_logger.close_db(conn)

@app.route('/api/v1/tasks/<task_id>/output', methods=['GET'])
def get_task_output(task_id):
    """Retrieves the output data for a specific completed task."""
    print(f"Request received for task output: {task_id}")
    db_config_path = os.getenv('DB_CONFIG_PATH', './db_config.ini')
    conn = db_logger.connect_db(db_config_path)
    if conn is None: return jsonify({"error": "Database connection failed"}), 500

    try:
        sql_query = "SELECT task_type FROM tasks WHERE task_id = %s;"
        task_type = None
        with conn.cursor() as cur:
            cur.execute(sql_query, (task_id,))
            result = cur.fetchone()
            if result: task_type = str(result[0])

        if not task_type: return jsonify({"error": f"Task {task_id} not found"}), 404

        if task_type == "vlm_extraction":
            output = db_logger.get_vlm_output(conn, task_id)
            return jsonify({"task_id": task_id, "task_type": task_type, "output_text": output})
        elif task_type == "ner_processing":
            output = db_logger.get_ner_output(conn, task_id)
            return jsonify({"task_id": task_id, "task_type": task_type, "output_json": output})
        elif task_type == "json_comparison":
            output = db_logger.get_comparison_output(conn, task_id)
            return jsonify({"task_id": task_id, "task_type": task_type, "output_comparison_json": output})
        elif task_type == "vlm_review":
            output = db_logger.get_review_output(conn, task_id)
            return jsonify({"task_id": task_id, "task_type": task_type, "output_review_json": output})
        else:
            return jsonify({"error": f"Unknown task type {task_type} for task {task_id}"}), 400
    finally:
        db_logger.close_db(conn)

@app.route('/api/v1/tasks/<task_id>/input_content', methods=['GET'])
def get_task_input_content(task_id):
    """Retrieves the input content (e.g., base64 image) for a specific task."""
    print(f"Request received for task input content: {task_id}")
    db_config_path = os.getenv('DB_CONFIG_PATH', './db_config.ini')
    conn = db_logger.connect_db(db_config_path)
    if conn is None: return jsonify({"error": "Database connection failed"}), 500

    try:
        content_type, content = db_logger.get_vlm_input_content(conn, task_id)
        if content_type is None or content is None:
             return jsonify({"error": f"Input content not found for task {task_id}"}), 404

        if content_type == 'image_base64':
            mime_type = "image/jpeg"
            return jsonify({"task_id": task_id, "content_type": content_type, "mime_type": mime_type, "base64_data": content})
        elif content_type == 'pdf_base64':
             return jsonify({"task_id": task_id, "content_type": content_type, "message": "PDF preview not directly supported via base64. Consider serving file."})
        elif content_type == 'url':
             return jsonify({"task_id": task_id, "content_type": content_type, "url": content})
        else:
            return jsonify({"error": f"Input content type '{content_type}' not suitable for display."}), 400

    except Exception as e:
        print(f"Error fetching input content for task {task_id}: {e}", file=sys.stderr)
        return jsonify({"error": "Failed to fetch input content"}), 500
    finally:
        db_logger.close_db(conn)


# --- Main Execution ---
if __name__ == '__main__':
    # TODO: Add command-line arguments for host, port, debug mode if needed
    app.run(debug=True, host='0.0.0.0', port=5001) # Run on port 5001 for example