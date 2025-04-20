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
        
        # Determine the final path and ensure directory exists
        final_write_path = None
        if output_file: # --output argument (full path) provided
            final_write_path = output_file
            output_dir_to_create = os.path.dirname(final_write_path)
        elif output_path: # --output-dir argument provided
            default_filename = generate_output_filename(file1, file2)
            final_write_path = os.path.join(output_path, default_filename)
            output_dir_to_create = output_path
        # If neither --output nor --output-dir is given, final_write_path remains None, and we don't write to file

        # Write file if a path was determined
        if final_write_path:
            # Ensure the target directory exists
            if output_dir_to_create and not os.path.exists(output_dir_to_create):
                 try:
                     os.makedirs(output_dir_to_create, exist_ok=True)
                 except OSError as e:
                     raise ValueError(f"Could not create output directory '{output_dir_to_create}'. {e}")

            # Write the comparison result
            with open(final_write_path, 'w') as f:
                json.dump(result, f, indent=2)
        return result
        
    except Exception as e:
        raise ValueError(f"Comparison failed: {str(e)}")
def run_json_comparison(data1: Dict, data2: Dict):
    """
    Compares two NER result dictionaries and returns the comparison result dictionary.

    Args:
        data1 (dict): The first NER result dictionary (e.g., {"entities": [...]}).
        data2 (dict): The second NER result dictionary.

    Returns:
        dict: A dictionary containing the comparison results.

    Raises:
        ValueError: If file loading or comparison fails.
    """
    try:
        # Data is now passed directly as arguments, no need to load files here
        # data1 = load_json_file(file1_path)
        # data2 = load_json_file(file2_path)
        # Assuming the structure is {"entities": [...]} based on feedback
        entities1 = data1.get("entities", [])
        entities2 = data2.get("entities", [])

        if not isinstance(entities1, list) or not isinstance(entities2, list):
             raise ValueError("Input JSON must contain an 'entities' list.")

        # Create dictionaries keyed by name+value
        dict1 = {f"{e.get('entity_name', '')}_{e.get('entity_value', '')}": e for e in entities1 if e.get('entity_name') and e.get('entity_value')}
        dict2 = {f"{e.get('entity_name', '')}_{e.get('entity_value', '')}": e for e in entities2 if e.get('entity_name') and e.get('entity_value')}

        all_keys = sorted(list(set(dict1.keys()).union(set(dict2.keys()))))

        comparison_results = []
        for key in all_keys:
            entity1 = dict1.get(key)
            entity2 = dict2.get(key)
            result_entity = {}

            if entity1 and entity2: # Match
                result_entity['entity_name'] = entity1['entity_name']
                result_entity['entity_value'] = entity1['entity_value']
                result_entity['comparison'] = "match"
                # Confidence calculation
                try:
                    c1 = float(entity1.get('confidence', 0)) / 100.0
                    c2 = float(entity2.get('confidence', 0)) / 100.0
                    c_final = (1.0 - ((1.0 - c1) * (1.0 - c2))) * 100.0
                    # Format to reasonable precision, e.g., 2 decimal places
                    result_entity['confidence'] = round(c_final, 2)
                except (ValueError, TypeError):
                     # Handle cases where confidence is missing or not a number
                     result_entity['confidence'] = "N/A" # Or some other indicator
            elif entity1: # Addition (in NER1 only)
                result_entity = entity1.copy() # Copy original entity
                result_entity['comparison'] = "addition"
                # Keep original confidence (ensure it's handled as number/string consistently)
                result_entity['confidence'] = entity1.get('confidence', 'N/A')
            elif entity2: # Omission (in NER2 only)
                result_entity = entity2.copy() # Copy original entity
                result_entity['comparison'] = "omission"
                 # Keep original confidence
                result_entity['confidence'] = entity2.get('confidence', 'N/A')

            if result_entity: # Ensure we have something to add
                comparison_results.append(result_entity)

        # Return in the same structure as input if needed, or just the list
        return {"entities": comparison_results}

    except Exception as e:
        # Re-raise exceptions to be handled by the caller
        # Adjust error message as paths are not used here directly
        raise ValueError(f"Comparison failed: {str(e)}")


# Remove duplicate main definition
# def main():
#     """CLI entry point for JSON comparison - Loads files and calls compare_json_files"""
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
        # Call the core comparison logic first
        result = run_json_comparison(args.file1, args.file2)

        # Handle file output based on CLI arguments
        output_file_cli = args.output
        output_dir_cli = args.output_dir
        final_write_path = None

        if output_file_cli: # --output argument (full path) provided
            final_write_path = output_file_cli
            output_dir_to_create = os.path.dirname(final_write_path)
        elif output_dir_cli: # --output-dir argument provided
            default_filename = generate_output_filename(args.file1, args.file2)
            final_write_path = os.path.join(output_dir_cli, default_filename)
            output_dir_to_create = output_dir_cli

        # Write file if a path was determined
        if final_write_path:
            # Ensure the target directory exists
            if output_dir_to_create and not os.path.exists(output_dir_to_create):
                 try:
                     os.makedirs(output_dir_to_create, exist_ok=True)
                 except OSError as e:
                     raise ValueError(f"Could not create output directory '{output_dir_to_create}'. {e}") # Re-raise

            # Write the comparison result
            with open(final_write_path, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"Comparison results saved to: {final_write_path}")

        print("Comparison successful. Results:")
        print(json.dumps(result, indent=2))
    except ValueError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
