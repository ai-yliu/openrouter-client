# OpenRouter API Client

A Python command-line tool to process text, PDF, and image files through the OpenRouter API.

## Features

- Process text, PDF, and image files
- Support for local files and remote URLs
- Configurable API parameters
- Readable output format
- Output to both screen and file

## Installation

### Prerequisites

- Python 3.6+
- Required Python packages:
  - requests
  - PyPDF2

Install the required packages:

```bash
pip install requests PyPDF2
```

### Setup

1. Clone or download this repository
2. Create a configuration file based on the sample_config.ini template
3. Obtain an API key from OpenRouter (https://openrouter.ai)

## Usage

### Command Line Interface

```bash
python -m openrouter.openrouter_client --input <input_file> --config <config_file> [--output <output_file>]
```

### Programmatic Usage

You can also use the OpenRouter API client programmatically in your Python code:

```python
from openrouter.config_handler import load_config
from openrouter.api_client import process_text, process_image, process_pdf
from openrouter.utils import determine_input_type, format_response

# Load configuration
config = load_config("path/to/config.ini")

# Process a text file
response = process_text("path/to/text_file.txt", config)

# Process an image
response = process_image("path/to/image.jpg", config)

# Process a PDF
response = process_pdf("path/to/document.pdf", config)

# Format the response
formatted_output = format_response(response)
print(formatted_output)
```

See `example_usage.py` for a complete example.

### Arguments

- `--input`: Path to the input file (image, PDF, or text) or a URL to an image/PDF
- `--config`: Path to the configuration file
- `--output`: (Optional) Path to the output file. If not provided, a default name will be generated based on the model name and input filename

### Examples

Process a local image file:
```bash
python -m openrouter.openrouter_client --input /path/to/image.jpg --config config.ini
```

Process a remote image URL:
```bash
python -m openrouter.openrouter_client --input https://example.com/image.jpg --config config.ini
```

Process a PDF file:
```bash
python -m openrouter.openrouter_client --input /path/to/document.pdf --config config.ini
```

Process a text file:
```bash
python -m openrouter.openrouter_client --input /path/to/document.txt --config config.ini
```

Specify an output file:
```bash
python -m openrouter.openrouter_client --input /path/to/image.jpg --config config.ini --output results.txt
```

## Configuration

Create a configuration file with the following parameters:

```ini
# Required parameters
API_KEY=your_api_key_here
BASE_URL=https://openrouter.ai
MODEL=openai/gpt-4o-2024-11-20

# Optional parameters
SYSTEM_PROMPT=You are a helpful assistant.
USER_PROMPT=
STREAM=false
TEMPERATURE=0.7
TOP_P=1.0
RESPONSE_FORMAT=text
```

### Configuration Parameters

#### Required Parameters

- `API_KEY`: Your OpenRouter API key
- `BASE_URL`: The base URL for the API (e.g., https://openrouter.ai)
- `MODEL`: The model to use (e.g., openai/gpt-4o-2024-11-20)

#### Optional Parameters

- `SYSTEM_PROMPT`: System prompt to set the behavior of the assistant
- `USER_PROMPT`: Additional user prompt to prepend to the input content
- `STREAM`: Whether to stream the response (true/false)
- `TEMPERATURE`: Controls randomness (0.0 to 1.0)
- `TOP_P`: Controls diversity via nucleus sampling (0.0 to 1.0)
- `RESPONSE_FORMAT`: Format of the response (text/json)

## Output

The output is formatted in a readable way and includes:

- The assistant's response
- Model information
- Token usage statistics

The output is both printed to the screen and saved to the specified output file.
