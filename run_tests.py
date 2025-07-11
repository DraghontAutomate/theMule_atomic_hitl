import unittest
import io
import sys
import re
import os
from typing import List, Dict, Any, Tuple, Optional
import argparse
import importlib

# Helper to extract docstrings and failure reasons
def get_test_docstring_and_failure_reason(test_method) -> Tuple[str, str, str]:
    """
    Extracts the test method name, its docstring, and a failure reason template from the docstring.
    The docstring is expected to have a specific format:
    First line: Brief description.
    Then, lines starting with "- What it tests:"
    Then, lines starting with "- Expected outcome:"
    Then, lines starting with "- Reason for failure:"
    """
    method_name = test_method.id().split('.')[-1]
    docstring = test_method.shortDescription() or "" # shortDescription() gets the first line of the docstring

    full_docstring = getattr(test_method, '_testMethodDoc', "") # Access full docstring

    what_tests = "Not specified."
    expected_outcome = "Not specified."
    failure_reason_template = "Reason not specified in docstring."

    if full_docstring:
        docstring_lines = full_docstring.split('\n')

        # Extract brief description from first line if not captured by shortDescription
        if not docstring and docstring_lines:
            docstring = docstring_lines[0].strip()

        what_lines = [line.replace("- What it tests:", "").strip() for line in docstring_lines if "- What it tests:" in line]
        if what_lines:
            what_tests = " ".join(what_lines)

        expected_lines = [line.replace("- Expected outcome:", "").strip() for line in docstring_lines if "- Expected outcome:" in line]
        if expected_lines:
            expected_outcome = " ".join(expected_lines)

        reason_lines = [line.replace("- Reason for failure:", "").strip() for line in docstring_lines if "- Reason for failure:" in line]
        if reason_lines:
            failure_reason_template = " ".join(reason_lines)

    if not docstring: # Fallback if shortDescription() was None
        docstring = method_name

    return docstring.strip(), f"What it tests: {what_tests}\nExpected outcome: {expected_outcome}", failure_reason_template


class TextTestResultWithDetails(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.test_details: List[Dict[str, Any]] = []

    def addSuccess(self, test):
        super().addSuccess(test)
        name, what, _ = get_test_docstring_and_failure_reason(test)
        self.test_details.append({
            "name": name,
            "status": "PASSED",
            "description": what,
            "reason": ""
        })

    def addFailure(self, test, err):
        super().addFailure(test, err)
        name, what, reason_template = get_test_docstring_and_failure_reason(test)
        # err is a tuple (type, value, traceback)
        err_msg = self._exc_info_to_string(err, test) # Get formatted traceback
        # Try to get a cleaner assertion message
        clean_err_msg = str(err[1]) # The error instance itself often has a good summary

        self.test_details.append({
            "name": name,
            "status": "FAILED",
            "description": what,
            "reason": f"{reason_template}\n```\n{clean_err_msg}\n```\n<details><summary>Full Traceback</summary>\n\n```\n{err_msg}\n```\n</details>"
        })

    def addError(self, test, err):
        super().addError(test, err)
        name, what, reason_template = get_test_docstring_and_failure_reason(test)
        err_msg = self._exc_info_to_string(err, test)
        clean_err_msg = str(err[1])

        self.test_details.append({
            "name": name,
            "status": "ERROR",
            "description": what,
            "reason": f"Test setup or an unexpected error occurred: {reason_template}\n```\n{clean_err_msg}\n```\n<details><summary>Full Traceback</summary>\n\n```\n{err_msg}\n```\n</details>"
        })

def generate_markdown_report(result: TextTestResultWithDetails, module_name: Optional[str] = None) -> str:
    """Generates a Markdown report from the test results."""
    report = io.StringIO()
    title_module = f" for Module: `{module_name}`" if module_name else ""
    report.write(f"# Test Execution Report{title_module}\n\n")

    total_tests = result.testsRun
    passed_tests = result.wasSuccessful() and total_tests == len(result.test_details) - len(result.failures) - len(result.errors) # A bit complex way to get successes
    # More direct way for successes:
    successes_count = 0
    for detail in result.test_details:
        if detail["status"] == "PASSED":
            successes_count +=1

    failures_count = len(result.failures)
    errors_count = len(result.errors)
    # successes_count = total_tests - failures_count - errors_count # This is more reliable

    report.write("## Summary\n")
    report.write(f"- **Total Tests Run:** {total_tests}\n")
    report.write(f"- **Passed:** {successes_count} ✅\n")
    report.write(f"- **Failed:** {failures_count} ❌\n")
    report.write(f"- **Errors:** {errors_count} ❗\n\n")

    if failures_count > 0 or errors_count > 0:
        report.write("## Details of Failures/Errors\n")
        for detail in result.test_details:
            if detail["status"] == "FAILED":
                report.write(f"### ❌ FAILED: {detail['name']}\n")
                report.write(f"**Description:** {detail['description']}\n\n")
                report.write(f"**Reason for Failure:**\n{detail['reason']}\n\n")
            elif detail["status"] == "ERROR":
                report.write(f"### ❗ ERROR: {detail['name']}\n")
                report.write(f"**Description:** {detail['description']}\n\n")
                report.write(f"**Reason for Error:**\n{detail['reason']}\n\n")

    if successes_count > 0 :
        report.write("## Passed Tests Summary\n")
        for detail in result.test_details:
            if detail['status'] == "PASSED":
                report.write(f"- ✅ {detail['name']}\n")
        report.write("\n")

    # Optionally, list all tests and their status
    report.write("## All Test Results\n")
    for detail in result.test_details:
        status_icon = "✅" if detail['status'] == "PASSED" else ("❌" if detail['status'] == "FAILED" else "❗")
        report.write(f"- {status_icon} **{detail['name']}**\n")
        report.write(f"  - Status: {detail['status']}\n")
        report.write(f"  - Description: {detail['description']}\n")
        if detail['status'] != "PASSED":
            report.write(f"  - Details: {detail['reason']}\n")
    report.write("\n")

    return report.getvalue()

def discover_and_run_tests(test_dir: str, module_filter: Optional[str] = None) -> TextTestResultWithDetails:
    """Discovers and runs tests, optionally filtering by module."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    if module_filter:
        # Attempt to load tests from a specific module file.
        # Assumes module_filter is a path like 'tests/test_config.py'
        # or a module name like 'tests.test_config'
        if os.path.isfile(module_filter) and module_filter.endswith(".py"):
            # Convert file path to module name
            # e.g. tests/test_config.py -> tests.test_config
            module_str = module_filter.replace(os.path.sep, '.')[:-3]
            try:
                # Ensure the parent directory of 'tests' is in sys.path if it's not already
                # This assumes the script is run from the repo root.
                # project_root = os.path.dirname(test_dir) # If test_dir is 'tests/'
                # if project_root not in sys.path and project_root != '':
                #    sys.path.insert(0, project_root)

                # Dynamically import the module
                # test_module = importlib.import_module(module_str)
                # module_suite = loader.loadTestsFromModule(test_module)

                # Simpler approach for single file if module name is predictable:
                # loader.discover expects a package name for the pattern if start_dir is not top-level
                # For a single file, it's easier to load directly if we know the module name
                # Or use pattern matching on the file name.
                # For simplicity with unittest discovery, let's assume module_filter is a pattern for the filename.
                # e.g. module_filter = "test_config.py"
                pattern = os.path.basename(module_filter) if module_filter.endswith(".py") else f"test_{module_filter}.py"
                # print(f"Discovering tests in '{test_dir}' with pattern '{pattern}'")
                module_suite = loader.discover(start_dir=test_dir, pattern=pattern, top_level_dir=os.path.dirname(test_dir))
                suite.addTest(module_suite)
            except Exception as e:
                print(f"Could not load tests for module filter '{module_filter}' (pattern: {pattern}): {e}")
                # Fallback to running all tests if specific module load fails
                # suite = loader.discover(test_dir, pattern="test_*.py", top_level_dir=os.path.dirname(test_dir))
        else: # Assume module_filter is a name like 'config' or 'core_logic'
            pattern = f"test_{module_filter}.py"
            # print(f"Discovering tests in '{test_dir}' with pattern '{pattern}'")
            module_suite = loader.discover(start_dir=test_dir, pattern=pattern, top_level_dir=os.path.dirname(test_dir))

            if module_suite.countTestCases() == 0:
                 print(f"Warning: No tests found for module filter '{module_filter}' (using pattern '{pattern}'). Running all tests instead.")
                 # Reset suite to be empty before loading all tests
                 suite = unittest.TestSuite()
                 all_tests_suite = loader.discover(test_dir, pattern="test_*.py", top_level_dir=os.path.dirname(test_dir))
                 suite.addTest(all_tests_suite)
            else:
                suite.addTest(module_suite)

    else: # Run all tests
        # print(f"Discovering all tests in '{test_dir}' with pattern 'test_*.py'")
        # The top_level_dir argument helps Python find modules correctly if 'tests' is not a top-level package itself.
        # Assuming the script is run from the repo root, and 'tests' is a directory in the root.
        # The parent of 'tests' (the repo root) should be what Python considers top-level for these imports.
        project_root_for_discovery = os.path.abspath(os.path.join(test_dir, ".."))
        suite = loader.discover(test_dir, pattern="test_*.py", top_level_dir=project_root_for_discovery)

    runner = unittest.TextTestRunner(resultclass=TextTestResultWithDetails, stream=io.StringIO()) # Suppress stdout during run
    result = runner.run(suite)
    return result


def main():
    parser = argparse.ArgumentParser(description="Run unit tests and generate a report.")
    parser.add_argument(
        "--module",
        type=str,
        help="Optional: Run tests only for a specific module (e.g., 'config', 'core_logic', or path 'tests/test_config.py')."
    )
    parser.add_argument(
        "--output",
        type=str,
        default="test_report.md",
        help="Filename for the Markdown report (default: test_report.md)."
    )
    parser.add_argument(
        "--test_dir",
        type=str,
        default="tests",
        help="Directory containing test files (default: tests)."
    )

    args = parser.parse_args()

    # Ensure the test directory is in sys.path for discovery if it's not standard
    # This helps if tests import things from src assuming repo root is in path
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__))) # Assumes run_tests.py is in repo root
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    # Also add src to path if it exists, for tests importing src modules
    src_path = os.path.join(repo_root, "src")
    if os.path.isdir(src_path) and src_path not in sys.path:
        sys.path.insert(0, src_path)


    print(f"Running tests from directory: {args.test_dir}")
    if args.module:
        print(f"Filtering for module: {args.module}")

    result = discover_and_run_tests(args.test_dir, args.module)

    report_content = generate_markdown_report(result, module_name=args.module)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(report_content)

    print(f"\nReport generated: {args.output}")

    # Exit with a non-zero status code if tests failed or had errors
    if not result.wasSuccessful():
        print("Some tests failed or had errors.")
        sys.exit(1)
    else:
        print("All tests passed successfully.")
        sys.exit(0)

if __name__ == "__main__":
    main()
