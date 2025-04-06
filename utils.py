"""
Utilities

Helper functions for the OpenRouter API client.
"""

import os
import mimetypes
import PyPDF2
import requests
from io import BytesIO

def determine_input_type(file_path):
    """
    Determine if the input file is an image, PDF, or text
    
    Args:
        file_path (str): Path to the input file
        
    Returns:
        str: "image", "pdf", or "text"
    """
    # For URLs, check the file extension
    if file_path.startswith(('http://', 'https://')):
        file_extension = os.path.splitext(file_path)[1].lower()
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
        if file_extension in image_extensions:
            return "image"
        elif file_extension == '.pdf':
            return "pdf"
        else:
            return "text"
    
    # For local files, use mimetypes
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type and mime_type.startswith('image/'):
        return "image"
    elif mime_type == 'application/pdf' or file_path.lower().endswith('.pdf'):
        return "pdf"
    else:
        return "text"

def extract_text_from_pdf(pdf_path):
    """
    Extract text from a PDF file
    
    Args:
        pdf_path (str): Path to the PDF file or URL
        
    Returns:
        str: Extracted text
    """
    try:
        # Handle remote PDFs
        if pdf_path.startswith(('http://', 'https://')):
            response = requests.get(pdf_path)
            response.raise_for_status()
            pdf_file = BytesIO(response.content)
        else:
            # Handle local PDFs
            pdf_file = open(pdf_path, 'rb')
        
        # Extract text from PDF
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        
        # Extract text from each page
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text += page.extract_text() + "\n\n"
        
        # Close the file if it's a local file
        if not pdf_path.startswith(('http://', 'https://')):
            pdf_file.close()
            
        return text
    except Exception as e:
        return f"Error extracting text from PDF: {str(e)}"

def generate_default_output_filename(input_file, model):
    """
    Generate a default output filename based on the model and input file
    
    Args:
        input_file (str): Path to the input file
        model (str): Model name (may contain special chars)
        
    Returns:
        str: Default output filename
    """
    # Extract the basename without extension
    basename = os.path.basename(input_file)
    name_without_ext = os.path.splitext(basename)[0]
    
    # Sanitize model name by replacing special characters with underscores
    safe_model = model.replace(':', '_').replace('/', '_')
    
    # Generate the output filename
    return f"{safe_model}_{name_without_ext}.txt"

def format_response(response):
    """
    Format the full API response for display
    
    Args:
        response (dict): The API response
        
    Returns:
        str: Formatted output with all relevant fields
    """
    if "error" in response:
        return f"Error: {response['error']}"
    
    try:
        output = "=" * 80 + "\n"
        output += "FULL RESPONSE\n"
        output += "=" * 80 + "\n\n"
        
        # Display all top-level fields
        for key, value in response.items():
            if key == "choices":
                continue  # Handle choices separately
            output += f"{key}: {str(value)}\n"
        
        # Handle choices array
        if "choices" in response and len(response["choices"]) > 0:
            output += "\n" + "-" * 80 + "\n"
            output += "MESSAGE DETAILS\n"
            output += "-" * 80 + "\n"
            
            for i, choice in enumerate(response["choices"]):
                output += f"\nChoice {i+1}:\n"
                message = choice.get("message", {})
                for msg_key, msg_value in message.items():
                    if msg_key == "content":
                        output += "\nContent:\n"
                        output += str(msg_value) + "\n"
                    else:
                        output += f"{msg_key}: {str(msg_value)}\n"
        
        # Add usage stats if available
        if "usage" in response:
            output += "\n" + "-" * 80 + "\n"
            output += "USAGE\n"
            output += "-" * 80 + "\n"
            usage = response["usage"]
            output += f"Total tokens: {usage.get('total_tokens', 'N/A')}\n"
            output += f"Prompt tokens: {usage.get('prompt_tokens', 'N/A')}\n"
            output += f"Completion tokens: {usage.get('completion_tokens', 'N/A')}\n"
        
        return output
        
    except Exception as e:
        return f"Error formatting response: {str(e)}\n\nRaw response: {response}"
