"""
Database Logger Module

Handles interaction with the PostgreSQL database for logging job and task details
for the openrouter-client workflows.
"""

import configparser
import sys
import psycopg2 # Or psycopg if using version 3+
from psycopg2 import sql # For safe dynamic SQL query construction
import json # For handling JSONB data types

# --- Database Connection ---

def connect_db(config_path="db_config.ini"):
    """
    Connects to the PostgreSQL database using credentials from the config file.

    Args:
        config_path (str): Path to the database configuration file.

    Returns:
        psycopg2.connection: The database connection object, or None if connection fails.
    """
    config = configparser.ConfigParser()
    if not config.read(config_path):
        print(f"Error: Database configuration file '{config_path}' not found or empty.", file=sys.stderr)
        return None

    try:
        db_config = config['postgresql']
        conn = psycopg2.connect(
            dbname=db_config.get('dbname'),
            user=db_config.get('user'),
            password=db_config.get('password'),
            host=db_config.get('host', 'localhost'), # Default host if not specified
            port=db_config.getint('port', 5432)      # Default port if not specified
        )
        print(f"Successfully connected to database '{db_config.get('dbname')}' on {db_config.get('host', 'localhost')}.")
        return conn
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error connecting to PostgreSQL database: {error}", file=sys.stderr)
        return None

def close_db(conn):
    """Closes the database connection."""
    if conn is not None:
        conn.close()
        print("Database connection closed.")

# --- Job Logging ---

def create_job(conn, workflow_name, input_source):
    """
    Creates a new job record in the 'jobs' table.

    Args:
        conn: Database connection object.
        workflow_name (str): Name of the workflow being run (e.g., 'compare_llms').
        input_source (str): The original input file/URL for the job.

    Returns:
        str: The UUID of the newly created job, or None if creation fails.
    """
    job_id = None
    sql_query = """
        INSERT INTO jobs (workflow_name, input_source, status)
        VALUES (%s, %s, 'started')
        RETURNING job_id;
    """
    try:
        with conn.cursor() as cur:
            cur.execute(sql_query, (workflow_name, input_source))
            job_id = cur.fetchone()[0]
            conn.commit()
            print(f"Created job record with ID: {job_id}")
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error creating job record: {error}", file=sys.stderr)
        conn.rollback() # Roll back the transaction on error
    return job_id

def update_job_status(conn, job_id, status, error_message=None):
    """
    Updates the status and optionally the end time and error message of a job.

    Args:
        conn: Database connection object.
        job_id (str): UUID of the job to update.
        status (str): The new status ('in-progress', 'completed', 'failed').
        error_message (str, optional): Error details if status is 'failed'.
    """
    sql_query = """
        UPDATE jobs
        SET status = %s,
            end_time = CASE WHEN %s IN ('completed', 'failed') THEN NOW() ELSE end_time END,
            error_message = %s
        WHERE job_id = %s;
    """
    try:
        with conn.cursor() as cur:
            cur.execute(sql_query, (status, status, error_message, job_id))
            conn.commit()
            print(f"Updated job {job_id} status to: {status}")
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error updating job status for {job_id}: {error}", file=sys.stderr)
        conn.rollback()

# --- Task Logging ---

def create_task(conn, job_id, task_order, task_type):
    """
    Creates a new task record in the 'tasks' table.

    Args:
        conn: Database connection object.
        job_id (str): UUID of the parent job.
        task_order (int): Sequence number of the task within the job.
        task_type (str): Type of the task ('vlm_extraction', 'ner_processing', 'json_comparison').

    Returns:
        str: The UUID of the newly created task, or None if creation fails.
    """
    task_id = None
    sql_query = """
        INSERT INTO tasks (job_id, task_order, task_type, status)
        VALUES (%s, %s, %s, 'pending')
        RETURNING task_id;
    """
    try:
        with conn.cursor() as cur:
            cur.execute(sql_query, (job_id, task_order, task_type))
            task_id = cur.fetchone()[0]
            conn.commit()
            print(f"Created task record {task_order} ({task_type}) with ID: {task_id} for job {job_id}")
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error creating task record for job {job_id}: {error}", file=sys.stderr)
        conn.rollback()
    return task_id

def update_task_status(conn, task_id, status, error_message=None):
    """
    Updates the status and optionally start/end times and error message of a task.

    Args:
        conn: Database connection object.
        task_id (str): UUID of the task to update.
        status (str): New status ('running', 'completed', 'failed').
        error_message (str, optional): Error details if status is 'failed'.
    """
    sql_query = """
        UPDATE tasks
        SET status = %s,
            start_time = CASE WHEN %s = 'running' AND start_time IS NULL THEN NOW() ELSE start_time END,
            end_time = CASE WHEN %s IN ('completed', 'failed') THEN NOW() ELSE end_time END,
            error_message = %s
        WHERE task_id = %s;
    """
    try:
        with conn.cursor() as cur:
            cur.execute(sql_query, (status, status, status, error_message, task_id))
            conn.commit()
            print(f"Updated task {task_id} status to: {status}")
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error updating task status for {task_id}: {error}", file=sys.stderr)
        conn.rollback()

# --- Task Detail Logging ---

# Placeholder functions for logging details - implementation needed
# These would construct INSERT statements for the respective task_details_* tables

def log_vlm_details(conn, task_id, details_dict):
    """
    Logs details specific to a VLM extraction task into the task_details_vlm table.

    Args:
        conn: Database connection object.
        task_id (str): UUID of the task.
        details_dict (dict): Dictionary containing VLM task details, e.g.:
            {
                'input_source': 'path/or/url',
                'input_content_type': 'image_base64' | 'pdf_base64' | 'text' | 'url',
                'input_content': 'base64_string_or_text_or_url',
                'api_request_model': 'model_name',
                'api_request_system_prompt': 'prompt text',
                'api_request_user_prompt': 'prompt text',
                'api_request_temperature': 0.7,
                'api_request_top_p': 1.0,
                'api_request_stream': False,
                'api_request_response_format': {'type': 'text'}, # JSONB
                'api_request_provider_options': {'option': 'value'} # JSONB
            }
    """
    sql_query = """
        INSERT INTO task_details_vlm (
            task_id, input_source, input_content_type, input_content,
            api_request_model, api_request_system_prompt, api_request_user_prompt,
            api_request_temperature, api_request_top_p, api_request_stream,
            api_request_response_format, api_request_provider_options
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
    """
    # Prepare data tuple, using .get() for optional fields to default to None if missing
    # Convert JSONB fields to JSON strings if they are dicts/lists
    response_format_json = None
    if isinstance(details_dict.get('api_request_response_format'), (dict, list)):
        response_format_json = json.dumps(details_dict['api_request_response_format'])

    provider_options_json = None
    if isinstance(details_dict.get('api_request_provider_options'), (dict, list)):
        provider_options_json = json.dumps(details_dict['api_request_provider_options'])

    data = (
        task_id,
        details_dict.get('input_source'),
        details_dict.get('input_content_type'),
        details_dict.get('input_content'),
        details_dict.get('api_request_model'),
        details_dict.get('api_request_system_prompt'),
        details_dict.get('api_request_user_prompt'),
        details_dict.get('api_request_temperature'),
        details_dict.get('api_request_top_p'),
        details_dict.get('api_request_stream'),
        response_format_json,
        provider_options_json
    )

    try:
        with conn.cursor() as cur:
            cur.execute(sql_query, data)
            conn.commit()
            print(f"Logged VLM details for task {task_id}")
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error logging VLM details for task {task_id}: {error}", file=sys.stderr)
        conn.rollback()


def log_ner_details(conn, task_id, details_dict):
    """
    Logs details specific to an NER processing task into the task_details_ner table.

    Args:
        conn: Database connection object.
        task_id (str): UUID of the task.
        details_dict (dict): Dictionary containing NER task details, e.g.:
            {
                'input_text': 'text processed by NER',
                'api_request_model': 'model_name',
                'api_request_system_prompt': 'prompt text',
                'api_request_user_prompt': 'prompt text',
                'api_request_temperature': 0.7,
                'api_request_top_p': 1.0,
                'api_request_stream': False,
                'api_request_response_format': {'type': 'json_object'}, # JSONB
                'api_request_provider_options': {'option': 'value'} # JSONB
            }
    """
    sql_query = """
        INSERT INTO task_details_ner (
            task_id, input_text,
            api_request_model, api_request_system_prompt, api_request_user_prompt,
            api_request_temperature, api_request_top_p, api_request_stream,
            api_request_response_format, api_request_provider_options
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
    """
    # Prepare data tuple, using .get() for optional fields
    response_format_json = None
    if isinstance(details_dict.get('api_request_response_format'), (dict, list)):
        response_format_json = json.dumps(details_dict['api_request_response_format'])

    provider_options_json = None
    if isinstance(details_dict.get('api_request_provider_options'), (dict, list)):
        provider_options_json = json.dumps(details_dict['api_request_provider_options'])

    data = (
        task_id,
        details_dict.get('input_text'),
        details_dict.get('api_request_model'),
        details_dict.get('api_request_system_prompt'),
        details_dict.get('api_request_user_prompt'),
        details_dict.get('api_request_temperature'),
        details_dict.get('api_request_top_p'),
        details_dict.get('api_request_stream'),
        response_format_json,
        provider_options_json
    )

    try:
        with conn.cursor() as cur:
            cur.execute(sql_query, data)
            conn.commit()
            print(f"Logged NER details for task {task_id}")
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error logging NER details for task {task_id}: {error}", file=sys.stderr)
        conn.rollback()

def log_comparison_details(conn, task_id, details_dict):
    """
    Logs details specific to a JSON comparison task into the task_details_comparison table.

    Args:
        conn: Database connection object.
        task_id (str): UUID of the task.
        details_dict (dict): Dictionary containing comparison task details, e.g.:
            {
                'input_json_path1': 'path/to/ner1_output.json',
                'input_json_path2': 'path/to/ner2_output.json'
            }
    """
    sql_query = """
        INSERT INTO task_details_comparison (task_id, input_json_path1, input_json_path2)
        VALUES (%s, %s, %s);
    """
    data = (
        task_id,
        details_dict.get('input_json_path1'),
        details_dict.get('input_json_path2')
    )

    try:
        with conn.cursor() as cur:
            cur.execute(sql_query, data)
            conn.commit()
            print(f"Logged Comparison details for task {task_id}")
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error logging Comparison details for task {task_id}: {error}", file=sys.stderr)
        conn.rollback()

# Placeholder function for updating output - implementation needed
# This would construct UPDATE statements for the respective task_details_* tables

def update_task_details_output(conn, task_id, task_type, output_data, api_response_id=None):
    """
    Updates the output field(s) and optionally api_response_id in the relevant
    task details table upon successful task completion.

    Args:
        conn: Database connection object.
        task_id (str): UUID of the task.
        task_type (str): Type of the task ('vlm_extraction', 'ner_processing', 'json_comparison').
        output_data (dict): Dictionary containing output data. Keys depend on task_type:
            - vlm_extraction: {'output_text': 'extracted text'}
            - ner_processing: {'output_json': {'entities': [...]}} # The actual JSON object
            - json_comparison: {'output_comparison_json': {'Category': {...}}} # The actual JSON object
        api_response_id (str, optional): The ID returned by the OpenRouter API (for VLM/NER).
    """
    sql_query = None
    data = None

    try:
        if task_type == 'vlm_extraction':
            sql_query = """
                UPDATE task_details_vlm
                SET output_text = %s,
                    api_response_id = %s
                WHERE task_id = %s;
            """
            data = (
                output_data.get('output_text'),
                api_response_id,
                task_id
            )
        elif task_type == 'ner_processing':
            sql_query = """
                UPDATE task_details_ner
                SET output_json = %s,
                    api_response_id = %s
                WHERE task_id = %s;
            """
            # Convert output dict/list to JSON string for JSONB column
            output_json_str = None
            if isinstance(output_data.get('output_json'), (dict, list)):
                 output_json_str = json.dumps(output_data['output_json'])

            data = (
                output_json_str,
                api_response_id,
                task_id
            )
        elif task_type == 'json_comparison':
            sql_query = """
                UPDATE task_details_comparison
                SET output_comparison_json = %s
                WHERE task_id = %s;
            """
             # Convert output dict/list to JSON string for JSONB column
            output_json_str = None
            if isinstance(output_data.get('output_comparison_json'), (dict, list)):
                 output_json_str = json.dumps(output_data['output_comparison_json'])

            data = (
                output_json_str,
                task_id
            )
        else:
            print(f"Warning: Unknown task_type '{task_type}' for updating output details for task {task_id}", file=sys.stderr)
            return # Do nothing if task type is unrecognized

        # Execute the update
        if sql_query and data:
            with conn.cursor() as cur:
                cur.execute(sql_query, data)
                conn.commit()
                print(f"Updated output details for task {task_id} ({task_type})")

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error updating output details for task {task_id} ({task_type}): {error}", file=sys.stderr)
        conn.rollback()

# Example usage (for testing purposes, can be removed later)
if __name__ == '__main__':
    print("Testing db_logger module...")
    # Assumes db_config.ini exists and is configured correctly
    # Assumes the necessary tables and ENUMs exist in the database
    connection = connect_db()
    if connection:
        print("\n--- Testing Job Creation ---")
        test_job_id = create_job(connection, 'test_workflow', './test_input.txt')

        if test_job_id:
            print("\n--- Testing Task Creation ---")
            test_task1_id = create_task(connection, test_job_id, 1, 'vlm_extraction')
            test_task2_id = create_task(connection, test_job_id, 2, 'json_comparison')

            print("\n--- Testing Status Updates ---")
            update_job_status(connection, test_job_id, 'in-progress')
            if test_task1_id:
                update_task_status(connection, test_task1_id, 'running')
                # Simulate task completion/failure
                update_task_status(connection, test_task1_id, 'completed')
                # update_task_status(connection, test_task1_id, 'failed', 'Simulated VLM error')

            if test_task2_id:
                 update_task_status(connection, test_task2_id, 'running')
                 update_task_status(connection, test_task2_id, 'failed', 'Simulated comparison error')

            # Simulate job completion/failure
            # update_job_status(connection, test_job_id, 'completed')
            update_job_status(connection, test_job_id, 'failed', 'Job failed due to task error')

        close_db(connection)
    else:
        print("Could not establish database connection for testing.")