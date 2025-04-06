#!/bin/bash
# Example script to demonstrate the OpenRouter API client with different file types

# Set the path to the configuration file
CONFIG_FILE="./example_config.ini"

# Check if the configuration file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Configuration file '$CONFIG_FILE' not found."
    echo "Please make sure you have created the configuration file with your API key."
    exit 1
fi

# Process a text file
echo "===== Processing Text File ====="
python -m openrouter.openrouter_client --input ./test_files/sample_text.txt --config "$CONFIG_FILE"
echo ""

# Process an image file (if available)
if [ -f "./test_files/sample_image.jpg" ]; then
    echo "===== Processing Image File ====="
    python -m openrouter.openrouter_client --input ./test_files/sample_image.jpg --config "$CONFIG_FILE"
    echo ""
else
    echo "Note: No sample image file found. To test image processing, add an image to ./test_files/sample_image.jpg"
fi

# Process a PDF file (if available)
if [ -f "./test_files/sample_document.pdf" ]; then
    echo "===== Processing PDF File ====="
    python -m openrouter.openrouter_client --input ./test_files/sample_document.pdf --config "$CONFIG_FILE"
    echo ""
else
    echo "Note: No sample PDF file found. To test PDF processing, add a PDF to ./test_files/sample_document.pdf"
fi

# Process a remote image URL
echo "===== Processing Remote Image URL ====="
python -m openrouter.openrouter_client --input "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Python-logo-notext.svg/1200px-Python-logo-notext.svg.png" --config "$CONFIG_FILE"
echo ""

echo "All examples completed."
