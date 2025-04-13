import unittest
import tempfile
from unittest.mock import patch
from llm_comparator import main

class TestLLMComparator(unittest.TestCase):
    @patch('subprocess.run')
    def test_full_workflow(self, mock_run):
        with tempfile.NamedTemporaryFile() as tmp:
            test_args = [
                "--input", "test.pdf",
                "--vlm-config", "vlm.ini",
                "--ner-config1", "ner1.ini",
                "--ner-config2", "ner2.ini",
                "--output", tmp.name
            ]
            
            # Mock successful subprocess calls
            mock_run.return_value.returncode = 0
            
            # Test successful execution
            main(test_args)
            
            # Verify subprocess calls
            self.assertEqual(mock_run.call_count, 4)
            
    @patch('subprocess.run')
    def test_error_handling(self, mock_run):
        mock_run.return_value.returncode = 1
        with self.assertRaises(SystemExit):
            main(["--input", "test.pdf", "--vlm-config", "vlm.ini",
                 "--ner-config1", "ner1.ini", "--ner-config2", "ner2.ini"])

if __name__ == '__main__':
    unittest.main()
