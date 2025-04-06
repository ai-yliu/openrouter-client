"""
Configuration Handler

Functions for loading and validating configuration files for the OpenRouter API client.
"""

import os
import sys

def load_config(config_file):
    """
    Load and validate configuration from a file.
    Handles multi-line values for all parameters while preserving exact formatting.
    
    Args:
        config_file (str): Path to the configuration file
        
    Returns:
        dict: Configuration parameters
    """
    config = {}
    current_key = None
    current_value = []
    
    with open(config_file, "r", encoding="utf-8") as f:
        for line in f:
            # Skip empty lines and comments
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
                
            # Handle new key-value pairs
            if '=' in line and current_key is None:
                key, value = line.split('=', 1)
                current_key = key.strip()
                current_value = [value.rstrip('\\\n')]
            # Handle value continuations
            elif current_key is not None:
                current_value.append(line.rstrip('\\\n'))
                
            # Finalize the current value if complete
            if current_key is not None and not line.rstrip().endswith('\\'):
                config[current_key] = '\n'.join(current_value).strip()
                current_key = None
    
    # Validate required parameters
    required_params = ["API_KEY", "BASE_URL", "MODEL"]
    missing_params = [param for param in required_params if param not in config]
    
    if missing_params:
        print(f"Error: Missing required configuration parameters: {', '.join(missing_params)}")
        sys.exit(1)
    
    # Set default values for optional parameters
    defaults = {
        "SYSTEM_PROMPT": "You are a helpful assistant.",
        "USER_PROMPT": "",
        "STREAM": "false",
        "TEMPERATURE": "0.7",
        "TOP_P": "1.0",
        "RESPONSE_FORMAT": "text"
    }
    
    for key, value in defaults.items():
        if key not in config:
            config[key] = value
    
    return config
