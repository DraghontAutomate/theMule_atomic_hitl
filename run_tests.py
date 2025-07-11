import unittest
import sys
import os
import io
from datetime import datetime

# Add src to sys.path to allow for direct import of modules
project_root = os.path.abspath(os.path.dirname(__file__))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)
# Add tests to sys.path to allow for discovery if tests are run from root
tests_path = os.path.join(project_root, 'tests')
if tests_path not in sys.path:
    sys.path.insert(0, tests_path)


class DetailedTestResult(unittest.TextTestResult):
    def __init__(self, stream, descriptions, verbosity):
        # Ensure the stream has writeln, adapting if necessary
        if not hasattr(stream, 'writeln'):
            class StreamAdapter:
                def __init__(self, s):
                    self._stream = s
                def write(self, msg):
                    self._stream.write(msg)
                def writeln(self, msg=""):
                    self._stream.write(msg + "\n")
                def flush(self):
                    self._stream.flush()
            stream = StreamAdapter(stream)
        super().__init__(stream, descriptions, verbosity)
        self.test_results = []
        self.test_times = {}

    def getDescription(self, test):
        """
        Attempts to get a human-readable description from the test's docstring.
        Falls back to the test method name.
        """
        doc_first_line = test.shortDescription()
        if self.descriptions and doc_first_line:
            return doc_first_line
        else:
            return str(test) # test.id().split('.')[-1]

    def startTest(self, test):
        self.test_start_time = datetime.now()
        super().startTest(test)
        if self.showAll:
            # Ensure self.stream is the adapted stream from __init__
            current_stream = self.stream if hasattr(self.stream, 'writeln') else self.super_stream
            current_stream.write(self.getDescription(test))
            current_stream.write(" ... ")
            current_stream.flush()

    def stopTest(self, test):
        super().stopTest(test)
        # Ensure test_start_time was set
        if hasattr(self, 'test_start_time'):
            test_duration = datetime.now() - self.test_start_time
            self.test_times[test.id()] = test_duration
        else:
            # This case might happen if startTest was not completed due to an early error
            self.test_times[test.id()] = None


    def addSuccess(self, test):
        super().addSuccess(test)
        self.test_results.append({
            "module": test.__class__.__module__.replace('tests.', ''), # Attempt to simplify module name
            "class": test.__class__.__name__,
            "method": test._testMethodName,
            "status": "PASS",
            "description": self.getDescription(test),
            "reason": "",
            "duration": self.test_times.get(test.id(), None) # Use get with default
        })

    def addFailure(self, test, err):
        super().addFailure(test, err)
        _, exception_value, _ = err
        self.test_results.append({
            "module": test.__class__.__module__.replace('tests.', ''),
            "class": test.__class__.__name__,
            "method": test._testMethodName,
            "status": "FAIL",
            "description": self.getDescription(test),
            "reason": f"AssertionError: {str(exception_value)}",
            "duration": self.test_times.get(test.id(), None) # Use get with default
        })

    def addError(self, test, err):
        super().addError(test, err)
        _, exception_value, _ = err
        self.test_results.append({
            "module": test.__class__.__module__.replace('tests.', ''),
            "class": test.__class__.__name__,
            "method": test._testMethodName,
            "status": "ERROR",
            "description": self.getDescription(test),
            "reason": f"Exception: {str(exception_value)}",
            "duration": self.test_times.get(test.id(), None) # Use get with default
        })

class TestReportRunner:
    def __init__(self, stream=sys.stdout, verbosity=1):
        self.stream = stream
        self.verbosity = verbosity

    def run(self, suite):
        # The DetailedTestResult will write to its own stream.
        # TextTestRunner needs a stream that supports writeln or we need to adapt.
        # Forcing our stream to be an object with a writeln method for compatibility.
        adapted_stream = stream
        if not hasattr(stream, 'writeln'):
            class StreamAdapter:
                def __init__(self, s):
                    self._stream = s
                def write(self, msg):
                    self._stream.write(msg)
                def writeln(self, msg=""):
                    self._stream.write(msg + "\n")
                def flush(self):
                    self._stream.flush()
            adapted_stream = StreamAdapter(stream)

        result = DetailedTestResult(adapted_stream, descriptions=True, verbosity=self.verbosity)
        suite.run(result)
        return result

def generate_report(test_result_data, overall_stats, stream):
    stream.write("\n" + "=" * 70 + "\n")
    stream.write(" " * 25 + "TEST EXECUTION REPORT\n")
    stream.write("=" * 70 + "\n")
    stream.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    stream.write(f"Total Tests: {overall_stats['total']}\n")
    stream.write(f"Passed: {overall_stats['passed']}\n")
    stream.write(f"Failed: {overall_stats['failed']}\n")
    stream.write(f"Errors: {overall_stats['errors']}\n")
    stream.write(f"Success Rate: {overall_stats['success_rate']:.2f}%\n")
    stream.write(f"Total Duration: {overall_stats['total_duration']}\n")
    stream.write("-" * 70 + "\n\n")

    if not test_result_data:
        stream.write("No tests were executed or found.\n")
        return

    # Group by module for better readability
    results_by_module = {}
    for res in test_result_data:
        module_key = res.get("module", "unknown_module")
        if module_key not in results_by_module:
            results_by_module[module_key] = []
        results_by_module[module_key].append(res)

    for module_name, results in results_by_module.items():
        stream.write(f"Module: {module_name}\n")
        stream.write("-" * (len(module_name) + 9) + "\n")
        for result in results:
            duration_str = f"{result['duration'].total_seconds():.3f}s" if result['duration'] else "N/A"
            stream.write(f"  Test: {result['class']}.{result['method']}\n")
            stream.write(f"    Status: {result['status']}\n")
            stream.write(f"    Description: {result['description']}\n")
            if result['status'] in ["FAIL", "ERROR"]:
                stream.write(f"    Reason: {result['reason']}\n")
            stream.write(f"    Duration: {duration_str}\n")
            stream.write("\n")
        stream.write("\n")
    stream.write("=" * 70 + "\n")
    stream.write("END OF REPORT\n")
    stream.write("=" * 70 + "\n")


def main(module_filter=None):
    # Discover tests
    loader = unittest.TestLoader()
    if module_filter:
        if module_filter == "themule_atomic_hitl":
            # Specific pattern for themule_atomic_hitl tests
            suite = loader.discover(start_dir=os.path.join(project_root, 'tests'), pattern='test_*.py')
            # This simple discovery might pick up all tests. We might need to refine this
            # if we add tests for llm_prompt_tool in a different file pattern or sub-directory.
            # For now, assume all tests in 'tests/' are for 'themule_atomic_hitl' if filtered.
            # A more robust way would be to inspect test modules.
        elif module_filter == "llm_prompt_tool":
            # Placeholder: Discover tests specifically for llm_prompt_tool
            # Example: loader.discover(start_dir=os.path.join(project_root, 'tests', 'llm_tool_tests'), pattern='test_*.py')
            # For now, if no such tests exist, it will be an empty suite.
            stream.write(f"Warning: Test discovery for module '{module_filter}' is not fully implemented yet or no tests exist.\n")
            suite = unittest.TestSuite() # Empty suite
        else:
            stream.write(f"Error: Unknown module filter '{module_filter}'.\n")
            return
    else: # Run all tests
        suite = loader.discover(start_dir=os.path.join(project_root, 'tests'), pattern='test_*.py')

    # Run tests and generate report
    # Use an in-memory stream for capturing unittest's default output if needed,
    # but our custom result class handles most of what we need.
    # However, TextTestRunner still prints dots/F/E, so capture that.
    runner_output_stream = io.StringIO()
    runner = TestReportRunner(stream=runner_output_stream, verbosity=2) # verbosity=2 for method names

    print(f"Running tests for: {module_filter if module_filter else 'all modules'}")
    print("Unittest Output:")

    # unittest's default runner prints to its stream directly.
    # We can let it print to stdout for now, or capture it if we want to suppress/reformat.
    # For simplicity, let TextTestRunner print its usual dots.
    # Our report will follow.

    # To use our custom result class for capturing details for the report:
    custom_result = DetailedTestResult(sys.stdout, True, 2) # stream, descriptions, verbosity

    overall_start_time = datetime.now()
    suite.run(custom_result)
    overall_end_time = datetime.now()

    total_duration = overall_end_time - overall_start_time

    # Print the runner's own output (dots, F, E, etc.)
    # print("\n--- Unittest Runner Standard Output ---")
    # print(runner_output_stream.getvalue())
    # print("--- End Unittest Runner Standard Output ---\n")

    # Prepare stats for the report
    passed_count = len([r for r in custom_result.test_results if r['status'] == 'PASS'])
    failed_count = len(custom_result.failures) # Failures from TextTestResult
    error_count = len(custom_result.errors) # Errors from TextTestResult
    total_tests = custom_result.testsRun

    success_rate = (passed_count / total_tests) * 100 if total_tests > 0 else 0.0

    overall_stats = {
        "total": total_tests,
        "passed": passed_count,
        "failed": failed_count,
        "errors": error_count,
        "success_rate": success_rate,
        "total_duration": total_duration
    }

    # Generate our custom report
    generate_report(custom_result.test_results, overall_stats, sys.stdout)

    # Return a status code (0 for success, 1 for failures/errors)
    return 0 if failed_count == 0 and error_count == 0 else 1

if __name__ == "__main__":
    # Example usage:
    # python run_tests.py
    # python run_tests.py themule_atomic_hitl
    # python run_tests.py llm_prompt_tool (will show warning for now)

    module_arg = None
    if len(sys.argv) > 1:
        module_arg = sys.argv[1]
        if module_arg not in ["themule_atomic_hitl", "llm_prompt_tool", None]:
            print(f"Invalid module argument: {module_arg}. Available: 'themule_atomic_hitl', 'llm_prompt_tool'.")
            sys.exit(2)

    exit_code = main(module_filter=module_arg)
    sys.exit(exit_code)
