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
    import openrouter_client
    import db_logger
    # import json # Already imported at top level

    # Connect to DB
    conn = db_logger.connect_db(db_config_path)
    if conn is None:
        print(f"Error: Could not connect to database in background workflow for job {job_id}", file=sys.stderr)
        return

    try:
        # Step 1: VLM Extraction
        task1_id = db_logger.create_task(conn, job_id, 1, 'vlm_extraction')
        print(f"DEBUG: Entering VLM details logging for task {task1_id}")
        # Log VLM input details (debug print)
        try:
            print(f"DEBUG: Importing config_handler and utils succeeded.")
            vlm_config_data = load_config(vlm_config_path)
            input_type = determine_input_type(input_file_path)
            input_content = input_file_path # Default for URL or text
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
                'input_source': input_file_path,
                'input_content_type': input_content_type,
                'input_content': input_content,
                'api_request_model': vlm_config_data.get('MODEL'),
                'api_request_system_prompt': vlm_config_data.get('SYSTEM_PROMPT'),
                'api_request_user_prompt': vlm_config_data.get('USER_PROMPT'),
                'api_request_temperature': float(vlm_config_data.get('TEMPERATURE', 0.7)),
                'api_request_top_p': float(vlm_config_data.get('TOP_P', 1.0)),
                'api_request_stream': vlm_config_data.get('STREAM', 'false').lower() == 'true',
                'api_request_response_format': json.loads(vlm_config_data['RESPONSE_FORMAT']) if vlm_config_data.get('RESPONSE_FORMAT', '').startswith('{') else {'type': vlm_config_data.get('RESPONSE_FORMAT', 'text')},
                'api_request_provider_options': json.loads(vlm_config_data['PROVIDER']) if vlm_config_data.get('PROVIDER', '').startswith('{') else None
            }
            print(f"DEBUG: About to call db_logger.log_vlm_details for task {task1_id}")
            print(f"DEBUG: Logging VLM details for task {task1_id}: {vlm_details}")
            db_logger.log_vlm_details(conn, task1_id, vlm_details)
        except Exception as log_err:
            print(f"Warning: Failed to log VLM input details for task {task1_id}: {log_err}", file=sys.stderr)
        print(f"DEBUG: Finished VLM details logging for task {task1_id}")
        db_logger.update_task_status(conn, task1_id, 'running')
        vlm_response = openrouter_client.run_openrouter_processing(input_file_path, vlm_config_path)
        if "error" in vlm_response:
            db_logger.update_task_status(conn, task1_id, 'failed', vlm_response["error"])
            db_logger.update_job_status(conn, job_id, 'failed', f"VLM step failed: {vlm_response['error']}")
            return
        db_logger.update_task_details_output(conn, task1_id, 'vlm_extraction', {'output_text': vlm_response.get("choices", [{}])[0].get("message", {}).get("content", "")})
        db_logger.update_task_status(conn, task1_id, 'completed')

        # Step 2: NER 1
        task2_id = db_logger.create_task(conn, job_id, 2, 'ner_processing')
        # Use the VLM output as input for NER
        vlm_text = vlm_response.get("choices", [{}])[0].get("message", {}).get("content", "")
        # Log NER1 input details (after vlm_text is set)
        try:
            ner1_config_data = load_config(ner_config1_path)
            ner1_details = {
                'input_text': vlm_text,
                'api_request_model': ner1_config_data.get('MODEL'),
                'api_request_system_prompt': ner1_config_data.get('SYSTEM_PROMPT'),
                'api_request_user_prompt': ner1_config_data.get('USER_PROMPT'),
                'api_request_temperature': float(ner1_config_data.get('TEMPERATURE', 0.7)),
                'api_request_top_p': float(ner1_config_data.get('TOP_P', 1.0)),
                'api_request_stream': ner1_config_data.get('STREAM', 'false').lower() == 'true',
                'api_request_response_format': json.loads(ner1_config_data['RESPONSE_FORMAT']) if ner1_config_data.get('RESPONSE_FORMAT', '').startswith('{') else {'type': ner1_config_data.get('RESPONSE_FORMAT', 'text')},
                'api_request_provider_options': json.loads(ner1_config_data['PROVIDER']) if ner1_config_data.get('PROVIDER', '').startswith('{') else None
            }
            print(f"DEBUG: Logging NER1 details for task {task2_id}: {ner1_details}")
            db_logger.log_ner_details(conn, task2_id, ner1_details)
        except Exception as log_err:
            print(f"Warning: Failed to log NER1 input details for task {task2_id}: {log_err}", file=sys.stderr)
        db_logger.update_task_status(conn, task2_id, 'running')
        # Use the VLM output as input for NER
        vlm_text = vlm_response.get("choices", [{}])[0].get("message", {}).get("content", "")
        # Save to temp file for compatibility with openrouter_client
        temp_vlm_txt = input_file_path + ".vlm.txt"
        with open(temp_vlm_txt, "w", encoding="utf-8") as f:
            f.write(vlm_text)
        ner1_response = openrouter_client.run_openrouter_processing(temp_vlm_txt, ner_config1_path)
        if "error" in ner1_response:
            db_logger.update_task_status(conn, task2_id, 'failed', ner1_response["error"])
            db_logger.update_job_status(conn, job_id, 'failed', f"NER1 step failed: {ner1_response['error']}")
            return
        db_logger.update_task_details_output(conn, task2_id, 'ner_processing', {'output_json': ner1_response})
        db_logger.update_task_status(conn, task2_id, 'completed')

        # Step 3: NER 2
        task3_id = db_logger.create_task(conn, job_id, 3, 'ner_processing')
        # Log NER2 input details
        try:
            ner2_config_data = load_config(ner_config2_path)
            ner2_details = {
                'input_text': vlm_text,
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
        ner2_response = openrouter_client.run_openrouter_processing(temp_vlm_txt, ner_config2_path)
        if "error" in ner2_response:
            db_logger.update_task_status(conn, task3_id, 'failed', ner2_response["error"])
            db_logger.update_job_status(conn, job_id, 'failed', f"NER2 step failed: {ner2_response['error']}")
            return
        db_logger.update_task_details_output(conn, task3_id, 'ner_processing', {'output_json': ner2_response})
        db_logger.update_task_status(conn, task3_id, 'completed')

        # Step 4: JSON Comparison
        import json_comparator
        task4_id = db_logger.create_task(conn, job_id, 4, 'json_comparison')
        # Define temp filenames before logging comparison details
        temp_ner1_json = input_file_path + ".ner1.json"
        temp_ner2_json = input_file_path + ".ner2.json"
        # Log Comparison input details
        try:
            comparison_details = {
                'input_json_path1': temp_ner1_json,
                'input_json_path2': temp_ner2_json
            }
            db_logger.log_comparison_details(conn, task4_id, comparison_details)
        except Exception as log_err:
            print(f"Warning: Failed to log Comparison input details for task {task4_id}: {log_err}", file=sys.stderr)
        db_logger.update_task_status(conn, task4_id, 'running')
        # Save NER outputs to temp files for compatibility (filenames already defined above)
        # import json # Already imported at top level
        with open(temp_ner1_json, "w", encoding="utf-8") as f:
            # Extract the actual content (assuming it's the NER JSON)
            ner1_content = ner1_response.get("choices", [{}])[0].get("message", {}).get("content", {})
            # If content is a string that needs parsing, parse it
            if isinstance(ner1_content, str):
                try:
                    ner1_content = json.loads(ner1_content)
                except json.JSONDecodeError:
                    print(f"Warning: NER1 content was not valid JSON: {ner1_content[:100]}...", file=sys.stderr)
                    ner1_content = {"error": "Invalid JSON content from NER1"}
            json.dump(ner1_content, f, indent=2) # Dump only the extracted content

        with open(temp_ner2_json, "w", encoding="utf-8") as f:
            # Extract the actual content (assuming it's the NER JSON)
            ner2_content = ner2_response.get("choices", [{}])[0].get("message", {}).get("content", {})
            # If content is a string that needs parsing, parse it
            if isinstance(ner2_content, str):
                 try:
                     ner2_content = json.loads(ner2_content)
                 except json.JSONDecodeError:
                     print(f"Warning: NER2 content was not valid JSON: {ner2_content[:100]}...", file=sys.stderr)
                     ner2_content = {"error": "Invalid JSON content from NER2"}
            json.dump(ner2_content, f, indent=2) # Dump only the extracted content
        comparison_result = json_comparator.run_json_comparison(temp_ner1_json, temp_ner2_json)
        db_logger.update_task_details_output(conn, task4_id, 'json_comparison', {'output_comparison_json': comparison_result})
        db_logger.update_task_status(conn, task4_id, 'completed')

        # Mark job as completed
        db_logger.update_job_status(conn, job_id, 'completed')
        print(f"Finished background workflow for job: {job_id}")

    except Exception as e:
        print(f"Error in background workflow for job {job_id}: {e}", file=sys.stderr)
        db_logger.update_job_status(conn, job_id, 'failed', str(e))
    finally:
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
    # SECURITY NOTE: Ensure proper validation/sanitization of filename
    # and potentially restrict access based on user session/job ID in a real app.
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        print(f"File not found for serving: {file_path}", file=sys.stderr)
        return "File not found", 404
    print(f"Serving uploaded file: {file_path}")
    # Guess MIME type for images and PDFs
    import mimetypes
    mime_type, _ = mimetypes.guess_type(file_path)
    # Serve from the absolute path defined in app config
    absolute_upload_folder = app.config['UPLOAD_FOLDER']
    # send_from_directory needs the directory path, not the full file path
    # It constructs the full path by joining the directory and filename
    print(f"DEBUG: Serving file '{filename}' from directory '{absolute_upload_folder}'")
    try:
        return send_from_directory(absolute_upload_folder, filename, mimetype=mime_type)
    except Exception as e:
        print(f"ERROR in send_from_directory: {e}", file=sys.stderr)
        return "Error serving file", 500 # Add return for the exception case
        return "Error serving file", 500

@app.route('/api/v1/jobs', methods=['POST'])
def start_job():
    """Handles file upload and starts the comparison workflow."""
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file: # Add checks for allowed file types if needed
        filename = str(uuid.uuid4()) + "_" + file.filename # Create unique filename
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        try:
            file.save(upload_path)
            print(f"File uploaded successfully to: {upload_path}")

            # Get config paths from environment variables with defaults
            vlm_config = os.getenv('VLM_CONFIG_PATH', './config/vlm_raw.ini')
            ner1_config = os.getenv('NER1_CONFIG_PATH', './config/llm_cat_qwen2.5-72b.ini')
            ner2_config = os.getenv('NER2_CONFIG_PATH', './config/llm_cat_llama-3.3.ini')
            db_config = os.getenv('DB_CONFIG_PATH', './db_config.ini')
            # Validate that config files exist after getting paths
            for cfg_path in [vlm_config, ner1_config, ner2_config, db_config]:
                if not os.path.exists(cfg_path):
                    print(f"Error: Configuration file '{cfg_path}' (from env or default) not found.", file=sys.stderr)
                    # Clean up uploaded file before returning error
                    if os.path.exists(upload_path):
                        try:
                            os.remove(upload_path)
                            print(f"Cleaned up uploaded file: {upload_path}")
                        except OSError as e:
                            print(f"Error cleaning up file {upload_path}: {e}", file=sys.stderr)
                    return jsonify({"error": f"Missing configuration file: {os.path.basename(cfg_path)}"}), 500
            # Validate that config files exist after getting paths
            for cfg_path in [vlm_config, ner1_config, ner2_config, db_config]:
                if not os.path.exists(cfg_path):
                    print(f"Error: Configuration file '{cfg_path}' (from env or default) not found.", file=sys.stderr)
                    return jsonify({"error": f"Missing configuration file: {os.path.basename(cfg_path)}"}), 500

            # Create initial job record in DB using db_logger
            conn = db_logger.connect_db(db_config)
            if conn is None:
                print("Error: Could not connect to database to create job.", file=sys.stderr)
                return jsonify({"error": "Database connection failed"}), 500
            try:
                job_id = db_logger.create_job(conn, 'compare_llms', upload_path)
                if not job_id:
                    print("Error: Failed to create job record in database.", file=sys.stderr)
                    return jsonify({"error": "Failed to create job record in database"}), 500
                print(f"Initiating job with DB job_id: {job_id}")
            finally:
                db_logger.close_db(conn)

            # Start background task
            thread = threading.Thread(target=run_comparison_workflow, args=(
                job_id, upload_path, vlm_config, ner1_config, ner2_config, db_config
            ))
            thread.start()
            active_jobs[job_id] = thread # Track the thread

            return jsonify({
                "message": "File uploaded and processing started.",
                "job_id": job_id,
                "uploaded_filename": filename # Send back filename for display URL
                }), 202 # Accepted

        except Exception as e:
            print(f"Error during file upload or job start: {e}", file=sys.stderr)
            # TODO: Clean up saved file if job start fails
            return jsonify({"error": f"Failed to process file: {e}"}), 500

    return jsonify({"error": "File processing failed."}), 400


@app.route('/api/v1/jobs/<job_id>/status', methods=['GET'])
def get_job_status(job_id):
    """Retrieves the status of a job and its tasks from the database."""
    print(f"Request received for job status: {job_id}")
    # Connect to DB and fetch job/task status
    db_config_path = os.getenv('DB_CONFIG_PATH', './db_config.ini') # Use env var
    # TODO: Add validation if db_config_path doesn't exist? Or rely on connect_db failure?
    # TODO: Add validation if db_config_path doesn't exist? Or rely on connect_db failure?
    conn = db_logger.connect_db(db_config_path)
    if conn is None:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        job_details = db_logger.get_job_status(conn, job_id)
        tasks = db_logger.get_tasks_for_job(conn, job_id)
        if not job_details:
            return jsonify({"error": f"Job {job_id} not found"}), 404
        status_data = {
            "job_id": job_id,
            "job_status": job_details.get("status"),
            "start_time": job_details.get("start_time"),
            "end_time": job_details.get("end_time"),
            "error_message": job_details.get("error_message"),
            "input_source": job_details.get("input_source"),
            "workflow_name": job_details.get("workflow_name"),
            "tasks": tasks
        }
        return jsonify(status_data)
    finally:
        db_logger.close_db(conn)

@app.route('/api/v1/tasks/<task_id>/output', methods=['GET'])
def get_task_output(task_id):
    """Retrieves the output data for a specific completed task."""
    print(f"Request received for task output: {task_id}")
    # Connect to DB and fetch task output
    db_config_path = os.getenv('DB_CONFIG_PATH', './db_config.ini') # Use env var
    # TODO: Add validation if db_config_path doesn't exist? Or rely on connect_db failure?
    # TODO: Add validation if db_config_path doesn't exist? Or rely on connect_db failure?
    conn = db_logger.connect_db(db_config_path)
    if conn is None:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        # Determine task type
        sql_query = "SELECT task_type FROM tasks WHERE task_id = %s;"
        task_type = None
        with conn.cursor() as cur:
            cur.execute(sql_query, (task_id,))
            result = cur.fetchone()
            if result:
                task_type = result[0]

        if not task_type:
            return jsonify({"error": f"Task {task_id} not found"}), 404

        # Fetch output based on task type
        if task_type == "vlm_extraction":
            output = db_logger.get_vlm_output(conn, task_id)
            return jsonify({"task_id": task_id, "task_type": task_type, "output_text": output})
        elif task_type == "ner_processing":
            output = db_logger.get_ner_output(conn, task_id)
            return jsonify({"task_id": task_id, "task_type": task_type, "output_json": output})
        elif task_type == "json_comparison":
            output = db_logger.get_comparison_output(conn, task_id)
            return jsonify({"task_id": task_id, "task_type": task_type, "output_comparison_json": output})
        else:
            return jsonify({"error": f"Unknown task type {task_type} for task {task_id}"}), 400
    finally:
        db_logger.close_db(conn)

@app.route('/api/v1/tasks/<task_id>/input_content', methods=['GET'])
def get_task_input_content(task_id):
    """Retrieves the input content (e.g., base64 image) for a specific task."""
    print(f"Request received for task input content: {task_id}")
    # Connect to DB and fetch task input content
    db_config_path = os.getenv('DB_CONFIG_PATH', './db_config.ini') # Use env var
    # TODO: Add validation if db_config_path doesn't exist? Or rely on connect_db failure?
    # TODO: Add validation if db_config_path doesn't exist? Or rely on connect_db failure?
    conn = db_logger.connect_db(db_config_path)
    if conn is None:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        # Currently only implemented for VLM tasks
        # TODO: Could potentially fetch input_text for NER tasks if needed
        content_type, content = db_logger.get_vlm_input_content(conn, task_id)

        if content_type is None or content is None:
             return jsonify({"error": f"Input content not found for task {task_id}"}), 404

        if content_type == 'image_base64':
            # Try to determine original image mime type (optional but helpful)
            # This requires storing original filename or mime type during upload/logging
            # For now, assume common types or return generic image type
            mime_type = "image/jpeg" # Default or fetch from DB if stored
            return jsonify({
                "task_id": task_id,
                "content_type": content_type, # Indicates it's base64
                "mime_type": mime_type, # Actual image mime type
                "base64_data": content
            })
        elif content_type == 'pdf_base64':
             # Decide how to handle PDF previews - maybe just return a link or message
             return jsonify({
                 "task_id": task_id,
                 "content_type": content_type,
                 "message": "PDF preview not directly supported via base64. Consider serving file."
             })
        elif content_type == 'url':
             return jsonify({
                 "task_id": task_id,
                 "content_type": content_type,
                 "url": content
             })
        else: # text or other
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