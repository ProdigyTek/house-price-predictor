#!/usr/bin/env python3
"""
Quick Test Status Checker

A simple command-line tool to quickly check test status without running
the full analyzer. Perfect for CI/CD pipelines and quick status checks.
"""

import xml.etree.ElementTree as ET
import sys
import os
from pathlib import Path
from datetime import datetime


def quick_check():
    """Quickly check test results and return status."""
    results_dir = Path("tests")
    
    # Find test result files
    xml_files = list(results_dir.glob("*_test_results.xml"))
    xml_files.extend(list(results_dir.glob("test_results.xml")))
    
    if not xml_files:
        print("❌ No test result files found!")
        print("Run tests first: python run_tests.py --mode unit")
        return 1
    
    total_tests = 0
    total_failures = 0
    total_errors = 0
    total_time = 0
    
    print("🔍 Quick Test Status Check")
    print("=" * 50)
    
    for xml_file in xml_files:
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            testsuite = root.find('.//testsuite') or root
            
            tests = int(testsuite.get('tests', 0))
            failures = int(testsuite.get('failures', 0))
            errors = int(testsuite.get('errors', 0))
            time = float(testsuite.get('time', 0))
            
            total_tests += tests
            total_failures += failures
            total_errors += errors
            total_time += time
            
            # Get test type from filename
            test_type = xml_file.stem.replace('_test_results', '').replace('test_results', 'general')
            
            # Status icon
            if failures == 0 and errors == 0:
                status = "✅ PASS"
            else:
                status = "❌ FAIL"
            
            print(f"{status} {test_type.upper()}: {tests} tests, {time:.2f}s")
            
        except Exception as e:
            print(f"❌ Error reading {xml_file}: {e}")
    
    print("=" * 50)
    
    # Overall status
    passed = total_tests - total_failures - total_errors
    success_rate = (passed / total_tests * 100) if total_tests > 0 else 0
    
    if total_failures == 0 and total_errors == 0:
        print(f"🎉 ALL TESTS PASSING! ({total_tests} tests, {total_time:.2f}s)")
        return 0
    else:
        print(f"⚠️ TESTS FAILING: {total_failures} failed, {total_errors} errors")
        print(f"📊 Success Rate: {success_rate:.1f}% ({passed}/{total_tests})")
        return 1


def show_failed_tests():
    """Show details of failed tests."""
    results_dir = Path("tests")
    xml_files = list(results_dir.glob("*_test_results.xml"))
    
    failed_tests = []
    
    for xml_file in xml_files:
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            
            for testcase in root.findall('.//testcase'):
                if testcase.find('failure') is not None or testcase.find('error') is not None:
                    name = testcase.get('name', 'Unknown')
                    classname = testcase.get('classname', '').split('.')[-1]
                    
                    failure = testcase.find('failure')
                    error = testcase.find('error')
                    
                    if failure is not None:
                        message = failure.get('message', failure.text or 'No message')[:100]
                        failed_tests.append(f"❌ {classname}::{name}\n   Failure: {message}...")
                    elif error is not None:
                        message = error.get('message', error.text or 'No message')[:100]
                        failed_tests.append(f"⚠️ {classname}::{name}\n   Error: {message}...")
        except Exception as e:
            continue
    
    if failed_tests:
        print("\n🚨 FAILED TESTS:")
        print("-" * 30)
        for test in failed_tests:
            print(test)
    else:
        print("\n✅ No failed tests found!")


def main():
    """Main entry point."""
    if len(sys.argv) > 1 and sys.argv[1] in ['--help', '-h']:
        print("""
Quick Test Status Checker

Usage:
  python quick_status.py          # Show overall status
  python quick_status.py --failed # Show failed test details

Exit codes:
  0 - All tests passing
  1 - Some tests failing or no results found
""")
        return
    
    # Change to the correct directory if needed
    if not Path("tests").exists():
        script_dir = Path(__file__).parent
        if (script_dir / "tests").exists():
            os.chdir(script_dir)
    
    # Quick status check
    exit_code = quick_check()
    
    # Show failed tests if requested or if there are failures
    if len(sys.argv) > 1 and sys.argv[1] == '--failed':
        show_failed_tests()
    elif exit_code != 0:
        show_failed_tests()
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()