"""Unit tests for JSON comparison module"""

import unittest
import os
import tempfile
import json
import sys
import os.path

# Adjust path to import from parent directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from json_comparator import compare_json_files, compare_category

class TestJsonComparator(unittest.TestCase):
    def test_category_comparison(self):
        # Test matching items
        self.assertEqual(
            compare_category(["A", "B"], ["a", "b"]),
            {"A": "match", "B": "match", "a": "match", "b": "match"}
        )
        
        # Test additions/omissions
        self.assertEqual(
            compare_category(["A", "B"], ["A", "C"]),
            {"A": "match", "B": "addition", "C": "omission"}
        )
        
        # Test empty lists
        self.assertEqual(compare_category([], []), {"": "match"})

    def test_file_comparison(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            file1 = os.path.join(tmpdir, "test1.json")
            file2 = os.path.join(tmpdir, "test2.json")
            
            with open(file1, 'w') as f:
                json.dump({"Items": ["A", "B"]}, f)
            with open(file2, 'w') as f:
                json.dump({"Items": ["a", "C"]}, f)
            
            # Test comparison
            result = compare_json_files(file1, file2)
            self.assertEqual(result, {
                "Items": {
                    "A": "match",
                    "B": "addition", 
                    "a": "match",
                    "C": "omission"
                }
            })
            
            # Test output file generation
            output_file = os.path.join(tmpdir, "output.json")
            compare_json_files(file1, file2, output_file=output_file)
            self.assertTrue(os.path.exists(output_file))
            with open(output_file, 'r') as f:
                saved_data = json.load(f)
                self.assertEqual(saved_data, result)

    def test_error_handling(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            invalid_file = os.path.join(tmpdir, "invalid.json")
            with open(invalid_file, 'w') as f:
                f.write("not valid json")
            
            with self.assertRaises(ValueError):
                compare_json_files(invalid_file, invalid_file)

if __name__ == '__main__':
    unittest.main()
