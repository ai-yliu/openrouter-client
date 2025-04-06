"""
API Client

Functions for interacting with the OpenRouter API.
"""

import requests
import base64
import json
# Handle both package import and direct script execution
try:
    from openrouter.utils import extract_text_from_pdf
except ImportError:
    from utils import extract_text_from_pdf

def call_openrouter_api(api_key, base_url, model, messages, config_options=None):
    """
    Call the OpenRouter API with the given parameters
    
    Args:
        api_key (str): The API key for authentication
        base_url (str): The base URL for the API
        model (str): The model to use
        messages (list): The messages to send to the API
        config_options (dict, optional): Additional configuration options
        
    Returns:
        dict: The API response
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Default request body
    request_body = {
        "model": model,
        "messages": messages,
        "stream": False
    }
    
    # Add additional configuration options if provided
    if config_options:
        for key, value in config_options.items():
            if value is not None:
                request_body[key] = value
    
    # Make the API request
    try:
        # Ensure the URL is properly formatted
        api_url = f"{base_url}/api/v1/chat/completions"
        if base_url.endswith('/'):
            api_url = f"{base_url}api/v1/chat/completions"
            
        response = requests.post(
            api_url,
            headers=headers,
            json=request_body,
            timeout=60
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

def process_text(text_file, config):
    """
    Process a text file through the OpenRouter API
    
    Args:
        text_file (str): Path to the text file
        config (dict): Configuration parameters
        
    Returns:
        dict: The API response
    """
    # Read the text file
    with open(text_file, "r", encoding="utf-8") as f:
        text_content = f.read()
    
    # Prepare messages
    messages = [
        {
            "role": "system",
            "content": config.get("SYSTEM_PROMPT", "You are a helpful assistant.")
        },
        {
            "role": "user",
            "content": config.get("USER_PROMPT", "") + "\n\n" + text_content if config.get("USER_PROMPT") else text_content
        }
    ]
    
    # Call the API
    return call_openrouter_api(
        config["API_KEY"],
        config["BASE_URL"],
        config["MODEL"],
        messages,
        {
            "temperature": float(config.get("TEMPERATURE", 0.7)),
            "top_p": float(config.get("TOP_P", 1.0)),
            "stream": config.get("STREAM", "false").lower() == "true",
            "response_format": json.loads(config["RESPONSE_FORMAT"]) if isinstance(config["RESPONSE_FORMAT"], str) and config["RESPONSE_FORMAT"].startswith('{') else {"type": "text"},
            "provider": json.loads(config["PROVIDER"]) if isinstance(config["PROVIDER"], str) and config["PROVIDER"].startswith('{') else {"data_collection": "deny"}
        }
    )

def process_pdf(pdf_path, config):
    """
    Process a PDF file through the OpenRouter API
    
    Args:
        pdf_path (str): Path to the PDF file or URL
        config (dict): Configuration parameters
        
    Returns:
        dict: The API response
    """
    # Extract text from the PDF
    pdf_text = extract_text_from_pdf(pdf_path)
    
    # Prepare messages
    messages = [
        {
            "role": "system",
            "content": config.get("SYSTEM_PROMPT", "You are a helpful assistant.")
        },
        {
            "role": "user",
            "content": config.get("USER_PROMPT", "") + "\n\n" + pdf_text if config.get("USER_PROMPT") else pdf_text
        }
    ]
    
    # Call the API
    return call_openrouter_api(
        config["API_KEY"],
        config["BASE_URL"],
        config["MODEL"],
        messages,
        {
            "temperature": float(config.get("TEMPERATURE", 0.7)),
            "top_p": float(config.get("TOP_P", 1.0)),
            "stream": config.get("STREAM", "false").lower() == "true",
            "provider": json.loads(config["PROVIDER"]) if isinstance(config["PROVIDER"], str) and config["PROVIDER"].startswith('{') else {"data_collection": "deny"},
            "response_format": json.loads(config["RESPONSE_FORMAT"]) if isinstance(config["RESPONSE_FORMAT"], str) and config["RESPONSE_FORMAT"].startswith('{') else {"type": "text"}
        }
    )

def process_image(image_path, config):
    """
    Process an image file through the OpenRouter API
    
    Args:
        image_path (str): Path to the image file or URL
        config (dict): Configuration parameters
        
    Returns:
        dict: The API response
    """
    # For local files, read and encode as base64
    if image_path.startswith(('http://', 'https://')):
        # For remote URLs, pass the URL directly
        image_content = image_path
    else:
        # For local files, read and encode as base64
        with open(image_path, 'rb') as image_file:
            image_data = image_file.read()
            image_content = f"data:image/jpeg;base64,{base64.b64encode(image_data).decode('utf-8')}"
    
    # Prepare messages with image content
    messages = [
        {
            "role": "system",
            "content": config.get("SYSTEM_PROMPT", "You are a helpful assistant.")
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": config.get("USER_PROMPT", "Describe this image in detail.")
                },
                {
                    "type": "image_url",
                    "image_url": {"url": image_content}
                }
            ]
        }
    ]
    
    # Call the API
    return call_openrouter_api(
        config["API_KEY"],
        config["BASE_URL"],
        config["MODEL"],
        messages,
        {
            "temperature": float(config.get("TEMPERATURE", 0.7)),
            "top_p": float(config.get("TOP_P", 1.0)),
            "stream": config.get("STREAM", "false").lower() == "true",
            "provider": json.loads(config["PROVIDER"]) if isinstance(config["PROVIDER"], str) and config["PROVIDER"].startswith('{') else {"data_collection": "deny"},
            "response_format": json.loads(config["RESPONSE_FORMAT"]) if isinstance(config["RESPONSE_FORMAT"], str) and config["RESPONSE_FORMAT"].startswith('{') else {"type": "text"}
        }
    )
