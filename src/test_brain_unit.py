import unittest
from nodes.brain_node import _validate_filename, _clean_content

class TestTheEditor(unittest.TestCase):

    def test_filename_validation(self):
        # 1. Valid cases
        valid, name = _validate_filename("plan.md")
        self.assertTrue(valid)
        self.assertEqual(name, "plan.md")

        valid, name = _validate_filename("notes.txt")
        self.assertTrue(valid)

        # 2. Path Traversal (Should strip path but remain valid if extension is ok)
        valid, name = _validate_filename("../../etc/passwd.txt")
        self.assertTrue(valid)
        self.assertEqual(name, "passwd.txt") # Should be basename

        # 3. Invalid Extensions
        valid, msg = _validate_filename("malware.exe")
        self.assertFalse(valid)
        self.assertIn("rejects this extension", msg)

        valid, msg = _validate_filename("script.sh")
        self.assertFalse(valid)

        valid, msg = _validate_filename("no_extension")
        self.assertFalse(valid)

    def test_content_cleaning_preamble(self):
        # 1. Basic Preamble stripping
        raw = "Certainly! Here is the plan:\n# Phase 1"
        clean = _clean_content(raw)
        self.assertEqual(clean, "# Phase 1")

        raw = "Sure, I can do that.\nData: 123"
        clean = _clean_content(raw)
        self.assertEqual(clean, "I can do that.\nData: 123") # "Sure," is removed, rest remains

        # Note: My regex was ^(Sure,)\s*. If "I can do that" follows immediately, it stays.
        # Let's verify exact behavior.
        # "Sure," matches. "I can do that." is the rest.

        raw = "Here is the file:\n{json: true}"
        clean = _clean_content(raw)
        self.assertEqual(clean, "{json: true}")

    def test_content_cleaning_extraction(self):
        # 2. Code Block Extraction (The Ghostwriter)
        raw = """
        Here is the code you asked for:
        ```markdown
        # The Real Content
        - Item 1
        ```
        Hope you like it!
        """
        clean = _clean_content(raw)
        self.assertEqual(clean, "# The Real Content\n- Item 1")

    def test_content_cleaning_python_extraction(self):
        raw = """
        Analysis complete.
        ```python
        print(\"Hello World\")
        ```
        """
        clean = _clean_content(raw)
        self.assertEqual(clean, 'print(\"Hello World\")')

if __name__ == '__main__':
    unittest.main()
