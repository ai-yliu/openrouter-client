"""
JSON Comparison Module for OpenRouter Client

Compares entity extraction results from different LLM runs
Identifies matches, additions and omissions between JSON outputs
"""

import json
import os
from typing import Dict, List, Union

def load_json_file(file_path: str) -> Dict:
    """Load and validate JSON file"""
    with open(file_path, 'r') as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Input must be a JSON object/dictionary")
    return data

def compare_category(list1: List, list2: List) -> Dict:
    """Compare items between two lists with case-insensitive matching"""
    result = {}
    
    # Handle empty lists case
    if not list1 and not list2:
        return {"": "match"}
    
    # Normalize for case-insensitive comparison
    list1_lower = [str(item).lower() for item in list1]
    list2_lower = [str(item).lower() for item in list2]
    
    # Check all items
    for item in list1 + list2:
        item_str = str(item)
        if item_str.lower() in list1_lower and item_str.lower() in list2_lower:
            result[item_str] = "match"
        elif item_str.lower() in list1_lower:
            result[item_str] = "addition"
        else:
            result[item_str] = "omission"
    return result

def compare_json_data(data1: Dict, data2: Dict) -> Dict:
    """Compare all categories in two JSON objects"""
    all_keys = set(data1.keys()).union(set(data2.keys()))
    return {
        key: compare_category(
            data1.get(key, []),
            data2.get(key, [])
        )
        for key in all_keys
    }

def generate_output_filename(file1: str, file2: str) -> str:
    """Generate default comparison filename"""
    base1 = os.path.splitext(os.path.basename(file1))[0]
    base2 = os.path.splitext(os.path.basename(file2))[0]
    return f"{base1}_{base2}_comparison.json"

def compare_json_files(
    file1: str,
    file2: str,
    output_path: str = None,
    output_file: str = None
) -> Dict:
    """
    Main function to compare two JSON files
    
    Args:
        file1: Path to first JSON file
        file2: Path to second JSON file  
        output_path: Optional directory for output
        output_file: Optional full output path
        
    Returns:
        Dict with comparison results
    """
    try:
        data1 = load_json_file(file1)
        data2 = load_json_file(file2)
        
        result = compare_json_data(data1, data2)
        
        if output_file or output_path:
            output_path = output_path or os.path.dirname(file1)
            output_file = output_file or generate_output_filename(file1, file2)
            os.makedirs(output_path, exist_ok=True)
            with open(os.path.join(output_path, output_file), 'w') as f:
                json.dump(result, f, indent=2)
        
        return result
        
    except Exception as e:
        raise ValueError(f"Comparison failed: {str(e)}")

def main():
    """CLI entry point for JSON comparison"""
    import argparse
    import sys
    parser = argparse.ArgumentParser(
        description='Compare two JSON files from LLM outputs'
    )
    parser.add_argument('file1', help='First JSON file path')
    parser.add_argument('file2', help='Second JSON file path')
    parser.add_argument('--output', help='Output file path')
    parser.add_argument('--output-dir', help='Output directory')
    
    args = parser.parse_args()
    
    try:
        result = compare_json_files(
            args.file1,
            args.file2,
            output_path=args.output_dir,
            output_file=args.output
        )
        print("Comparison successful. Results:")
        print(json.dumps(result, indent=2))
    except ValueError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
