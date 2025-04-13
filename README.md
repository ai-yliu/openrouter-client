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
python -m openrouter.openrouter_client \\
  --input <input_file> \\
  --config <config_file> \\
  [--output <output_file>] \\
  [--output-path <output_directory>] \\
  [--debug Y/N]
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
- `--output`: (Optional) Full path to the output file including filename (mutually exclusive with --output-path)
- `--output-path`: (Optional) Directory path where output file should be saved (uses auto-generated filename, mutually exclusive with --output)
- `--debug`: (Optional) Include prompts in output file (Y/N, default: N)

Note: Only one of --output or --output-path may be used at a time

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

## LLM Comparison Tool (`compare-llms`)

This tool orchestrates a workflow to compare the Named Entity Recognition (NER) results from two different LLMs on text extracted from an input image or PDF file. It utilizes the `openrouter-client` for text extraction (using a VLM) and NER processing, and the `compare-json` tool for the final comparison. It also logs the progress and details of each job and its steps to a configured PostgreSQL database.

### Command Line Usage

```bash
# Basic usage with required arguments
compare-llms \\
  --input document.pdf \\
  --vlm-config config_vlm.ini \\
  --ner-config1 config_ner1.ini \\
  --ner-config2 config_ner2.ini

# Specify final output file path
compare-llms \\
  --input image.png \\
  --vlm-config config_vlm.ini \\
  --ner-config1 config_ner1.ini \\
  --ner-config2 config_ner2.ini \\
  --output /path/to/results/comparison_result.json

# Specify output directory (uses default filename like <input_basename>_comparison.json)
compare-llms \\
  --input document.pdf \\
  --vlm-config config_vlm.ini \\
  --ner-config1 config_ner1.ini \\
  --ner-config2 config_ner2.ini \\
  --output-path ./comparison_outputs

# Keep temporary files for debugging
compare-llms \\
  --input document.pdf \\
  --vlm-config config_vlm.ini \\
  --ner-config1 config_ner1.ini \\
  --ner-config2 config_ner2.ini \\
  --debug

# Use a specific temporary directory
compare-llms \\
  --input document.pdf \\
  --vlm-config config_vlm.ini \\
  --ner-config1 config_ner1.ini \\
  --ner-config2 config_ner2.ini \\
  --temp-dir /path/to/custom/temp

# Enable database logging (assuming db_config.ini exists)
compare-llms \\
  --input document.pdf \\
  --vlm-config config_vlm.ini \\
  --ner-config1 config_ner1.ini \\
  --ner-config2 config_ner2.ini \\
  --db-config db_config.ini
```

### Arguments

*   `--input` (Required): Path or URL to the input image or PDF file.
*   `--vlm-config` (Required): Path to the configuration file for the VLM text extraction step.
*   `--ner-config1` (Required): Path to the configuration file for the first NER LLM. Ensure this config specifies JSON output format.
*   `--ner-config2` (Required): Path to the configuration file for the second NER LLM. Ensure this config specifies JSON output format.
*   `--output` (Optional): Full path (directory + filename) for the final JSON comparison result file. Mutually exclusive with `--output-path`.
*   `--output-path` (Optional): Directory path where the final JSON comparison result file should be saved (uses an auto-generated filename like `<input_basename>_comparison.json`). Mutually exclusive with `--output`.
*   `--temp-dir` (Optional): Directory path to store intermediate files (VLM output, NER outputs). If not provided, uses the system's default temporary directory.
*   `--debug` (Optional): If this flag is present, intermediate temporary files will *not* be deleted after the workflow completes.
*   `--db-config` (Optional): Path to the database configuration file (default: `db_config.ini`). If provided and valid, the tool will log job and task details to the specified PostgreSQL database. See `db_config.ini.template` for the required format.

### Workflow

1.  Extracts text from the input image/PDF using the VLM specified in `--vlm-config`.
2.  Runs NER on the extracted text using the first LLM specified in `--ner-config1`.
3.  Runs NER on the extracted text using the second LLM specified in `--ner-config2`.
4.  Compares the JSON outputs from the two NER runs using the `compare-json` logic.
5.  Saves the final comparison result.

## JSON Comparison Tool Usage

The package includes a tool to compare JSON outputs from different LLM runs:

### Command Line Usage
```bash
compare-json file1.json file2.json

# Save to specific file
compare-json file1.json file2.json --output comparison.json

# Save to directory (auto-generated filename)
compare-json file1.json file2.json --output-dir ./comparisons
```

### Programmatic Usage
```python
from json_comparator import compare_json_files

# Compare files and get results dictionary
result = compare_json_files("output1.json", "output2.json")

# Save comparison to file
compare_json_files("llm1.json", "llm2.json", 
                   output_file="comparison.json")

# Save to directory with auto-generated filename  
compare_json_files("run1.json", "run2.json",
                   output_path="./results")
```

### Features
- Case-insensitive comparison
- Preserves original casing in output  
- Identifies:
  - `match`: Items appearing in both files
  - `addition`: Items only in first file  
  - `omission`: Items only in second file
- Handles empty lists as matches
  
### Sample Output
```json
{
  "Entities": {
    "Company A": "match",
    "Company B": "addition",
    "COMPANY C": "omission"
  },
  "EmptyList": {"": "match"}
}

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
