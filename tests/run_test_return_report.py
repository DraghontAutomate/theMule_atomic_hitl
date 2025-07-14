import unittest
import sys
import os
import json
from datetime import datetime

# Add src to sys.path to allow for direct import of modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

class ScriptableTestResult(unittest.TextTestResult):
    def __init__(self, stream, descriptions, verbosity):
        super().__init__(stream, descriptions, verbosity)
        self.results = []

    def getDescription(self, test):
        doc = test.shortDescription()
        if doc:
            return doc
        return str(test)

    def addSuccess(self, test):
        super().addSuccess(test)
        self.results.append(self._get_test_details(test, 'PASS'))

    def addFailure(self, test, err):
        super().addFailure(test, err)
        _, exception_value, _ = err
        reason = f"AssertionError: {str(exception_value)}"
        self.results.append(self._get_test_details(test, 'FAIL', reason))

    def addError(self, test, err):
        super().addError(test, err)
        _, exception_value, _ = err
        reason = f"Exception: {str(exception_value)}"
        self.results.append(self._get_test_details(test, 'ERROR', reason))

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.results.append(self._get_test_details(test, 'SKIP', reason))

    def _get_test_details(self, test, status, reason=""):
        docstring = test.shortDescription() or ''
        technical_detail, functional_detail = self._parse_docstring(docstring)
        return {
            "module": test.__class__.__module__,
            "class": test.__class__.__name__,
            "method": test._testMethodName,
            "status": status,
            "technical_detail": technical_detail,
            "functional_detail": functional_detail,
            "reason": reason
        }

    def _parse_docstring(self, docstring):
        if not docstring:
            return "No description available.", "No description available."

        # Look for explicit markers, otherwise split by newline
        if '[TECH]' in docstring and '[FUNC]' in docstring:
            tech_part = docstring.split('[TECH]', 1)[1].split('[FUNC]', 1)[0].strip()
            func_part = docstring.split('[FUNC]', 1)[1].strip()
            return tech_part, func_part

        # Fallback to simple newline split
        parts = docstring.split('\n', 1)
        technical = parts[0].strip()
        functional = parts[1].strip() if len(parts) > 1 else "Not specified."
        return technical, functional

def run_tests_and_generate_report(modules=None):
    """
    Runs tests for the specified modules and generates a scriptable report.
    """
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    test_dir = os.path.dirname(__file__)

    if not modules:
        # Discover all tests if no modules are specified
        suite = loader.discover(start_dir=test_dir, pattern='test_*.py')
    else:
        for module_name in modules:
            pattern = f"test_{module_name}.py"
            discovered_suite = loader.discover(start_dir=test_dir, pattern=pattern)
            suite.addTest(discovered_suite)

    runner = unittest.TextTestRunner(resultclass=ScriptableTestResult, stream=sys.stderr)
    result = runner.run(suite)

    report = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "summary": {
            "total": result.testsRun,
            "passed": len([r for r in result.results if r['status'] == 'PASS']),
            "failed": len(result.failures),
            "errors": len(result.errors),
            "skipped": len(result.skipped),
        },
        "tests": result.results
    }

    return report

if __name__ == '__main__':
    # Default to all modules if no arguments are provided
    modules_to_test = sys.argv[1:] if len(sys.argv) > 1 else None

    report_data = run_tests_and_generate_report(modules=modules_to_test)

    print(json.dumps(report_data, indent=4))

    # Exit with a non-zero status code if there were failures or errors
    if report_data['summary']['failed'] > 0 or report_data['summary']['errors'] > 0:
        sys.exit(1)
