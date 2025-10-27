#!/usr/bin/env python3
"""
Test Results Viewer and Analyzer

This tool provides comprehensive visualization and analysis of test results
from the House Price Prediction MLOps project test suite.

Features:
- Parse JUnit XML results
- Generate HTML reports
- Show test coverage statistics
- Display performance metrics
- Create test trends analysis
"""

import xml.etree.ElementTree as ET
import json
import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import os


class TestResultsAnalyzer:
    """Comprehensive test results analysis and reporting."""
    
    def __init__(self, results_dir: str = "tests"):
        """Initialize the analyzer with results directory."""
        self.results_dir = Path(results_dir)
        self.test_data = {}
        
    def parse_junit_xml(self, xml_file: Path) -> Dict:
        """Parse JUnit XML file and extract test information."""
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            
            # Find testsuite element
            testsuite = root.find('.//testsuite')
            if testsuite is None:
                testsuite = root
            
            suite_data = {
                'name': testsuite.get('name', 'Unknown'),
                'tests': int(testsuite.get('tests', 0)),
                'failures': int(testsuite.get('failures', 0)),
                'errors': int(testsuite.get('errors', 0)),
                'skipped': int(testsuite.get('skipped', 0)),
                'time': float(testsuite.get('time', 0)),
                'timestamp': testsuite.get('timestamp', ''),
                'hostname': testsuite.get('hostname', ''),
                'testcases': []
            }
            
            # Parse individual test cases
            for testcase in testsuite.findall('.//testcase'):
                case_data = {
                    'classname': testcase.get('classname', ''),
                    'name': testcase.get('name', ''),
                    'time': float(testcase.get('time', 0)),
                    'status': 'passed'
                }
                
                # Check for failures, errors, or skips
                if testcase.find('failure') is not None:
                    case_data['status'] = 'failed'
                    case_data['failure'] = testcase.find('failure').text
                elif testcase.find('error') is not None:
                    case_data['status'] = 'error'
                    case_data['error'] = testcase.find('error').text
                elif testcase.find('skipped') is not None:
                    case_data['status'] = 'skipped'
                    case_data['skipped'] = testcase.find('skipped').text
                
                suite_data['testcases'].append(case_data)
            
            return suite_data
            
        except Exception as e:
            print(f"Error parsing {xml_file}: {e}")
            return {}
    
    def load_all_results(self) -> Dict:
        """Load all test result files from the results directory."""
        results = {}
        
        # Find all XML result files
        xml_files = list(self.results_dir.glob("*_test_results.xml"))
        xml_files.extend(list(self.results_dir.glob("test_results.xml")))
        
        for xml_file in xml_files:
            # Extract test type from filename
            test_type = xml_file.stem.replace('_test_results', '').replace('test_results', 'general')
            results[test_type] = self.parse_junit_xml(xml_file)
        
        return results
    
    def generate_summary_report(self, results: Dict) -> str:
        """Generate a comprehensive summary report."""
        report = []
        report.append("=" * 80)
        report.append("🧪 TEST RESULTS ANALYSIS REPORT")
        report.append("=" * 80)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # Overall statistics
        total_tests = sum(suite.get('tests', 0) for suite in results.values())
        total_failures = sum(suite.get('failures', 0) for suite in results.values())
        total_errors = sum(suite.get('errors', 0) for suite in results.values())
        total_skipped = sum(suite.get('skipped', 0) for suite in results.values())
        total_passed = total_tests - total_failures - total_errors - total_skipped
        total_time = sum(suite.get('time', 0) for suite in results.values())
        
        report.append("📊 OVERALL SUMMARY")
        report.append("-" * 40)
        report.append(f"Total Tests:     {total_tests}")
        report.append(f"✅ Passed:       {total_passed} ({total_passed/total_tests*100:.1f}%)" if total_tests > 0 else "✅ Passed:       0")
        report.append(f"❌ Failed:       {total_failures}")
        report.append(f"⚠️  Errors:       {total_errors}")
        report.append(f"⏭️  Skipped:      {total_skipped}")
        report.append(f"⏱️  Total Time:   {total_time:.2f}s")
        report.append("")
        
        # Status indicator
        if total_failures == 0 and total_errors == 0:
            report.append("🎉 STATUS: ALL TESTS PASSING! 🎉")
        else:
            report.append("⚠️  STATUS: SOME TESTS FAILING")
        report.append("")
        
        # Per-suite breakdown
        report.append("📋 TEST SUITE BREAKDOWN")
        report.append("-" * 40)
        
        for suite_name, suite_data in results.items():
            if not suite_data:
                continue
                
            tests = suite_data.get('tests', 0)
            failures = suite_data.get('failures', 0)
            errors = suite_data.get('errors', 0)
            skipped = suite_data.get('skipped', 0)
            passed = tests - failures - errors - skipped
            time = suite_data.get('time', 0)
            
            status_icon = "✅" if failures == 0 and errors == 0 else "❌"
            
            report.append(f"{status_icon} {suite_name.upper()}")
            report.append(f"   Tests: {tests} | Passed: {passed} | Failed: {failures} | Errors: {errors}")
            report.append(f"   Time: {time:.2f}s | Success Rate: {passed/tests*100:.1f}%" if tests > 0 else f"   Time: {time:.2f}s")
            report.append("")
        
        # Performance analysis
        if results:
            report.append("⚡ PERFORMANCE ANALYSIS")
            report.append("-" * 40)
            
            # Slowest tests
            all_testcases = []
            for suite_data in results.values():
                if suite_data and 'testcases' in suite_data:
                    for testcase in suite_data['testcases']:
                        testcase['suite'] = suite_data.get('name', 'Unknown')
                        all_testcases.append(testcase)
            
            if all_testcases:
                slowest_tests = sorted(all_testcases, key=lambda x: x.get('time', 0), reverse=True)[:5]
                
                report.append("🐌 Slowest Tests:")
                for i, test in enumerate(slowest_tests, 1):
                    name = test.get('name', 'Unknown')
                    time = test.get('time', 0)
                    classname = test.get('classname', '').split('.')[-1]
                    report.append(f"   {i}. {classname}::{name} - {time:.3f}s")
                
                report.append("")
                
                # Average test time
                avg_time = sum(t.get('time', 0) for t in all_testcases) / len(all_testcases)
                report.append(f"📈 Average Test Time: {avg_time:.3f}s")
                report.append("")
        
        # Failed tests details
        failed_tests = []
        for suite_data in results.values():
            if suite_data and 'testcases' in suite_data:
                for testcase in suite_data['testcases']:
                    if testcase.get('status') in ['failed', 'error']:
                        failed_tests.append(testcase)
        
        if failed_tests:
            report.append("🚨 FAILED TESTS DETAILS")
            report.append("-" * 40)
            for test in failed_tests:
                name = test.get('name', 'Unknown')
                classname = test.get('classname', '').split('.')[-1]
                status = test.get('status', 'unknown')
                report.append(f"❌ {classname}::{name} ({status})")
                if 'failure' in test:
                    report.append(f"   Failure: {test['failure'][:100]}...")
                if 'error' in test:
                    report.append(f"   Error: {test['error'][:100]}...")
                report.append("")
        
        return "\n".join(report)
    
    def generate_html_report(self, results: Dict) -> str:
        """Generate an HTML report for better visualization."""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Test Results Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header {{ text-align: center; color: #333; border-bottom: 2px solid #eee; padding-bottom: 20px; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
        .metric {{ background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; border-left: 4px solid #007bff; }}
        .metric.passed {{ border-left-color: #28a745; }}
        .metric.failed {{ border-left-color: #dc3545; }}
        .metric.skipped {{ border-left-color: #ffc107; }}
        .suite {{ margin: 20px 0; padding: 15px; border-radius: 8px; background: #f8f9fa; }}
        .suite-header {{ font-weight: bold; margin-bottom: 10px; }}
        .test-case {{ padding: 8px; margin: 5px 0; border-radius: 4px; }}
        .test-case.passed {{ background: #d4edda; color: #155724; }}
        .test-case.failed {{ background: #f8d7da; color: #721c24; }}
        .test-case.error {{ background: #f8d7da; color: #721c24; }}
        .test-case.skipped {{ background: #fff3cd; color: #856404; }}
        .status-indicator {{ font-size: 24px; margin: 20px 0; text-align: center; }}
        .timestamp {{ color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧪 Test Results Report</h1>
            <p class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
"""
        
        # Calculate overall metrics
        total_tests = sum(suite.get('tests', 0) for suite in results.values())
        total_failures = sum(suite.get('failures', 0) for suite in results.values())
        total_errors = sum(suite.get('errors', 0) for suite in results.values())
        total_skipped = sum(suite.get('skipped', 0) for suite in results.values())
        total_passed = total_tests - total_failures - total_errors - total_skipped
        total_time = sum(suite.get('time', 0) for suite in results.values())
        
        # Status indicator
        overall_status = "🎉 ALL TESTS PASSING!" if total_failures == 0 and total_errors == 0 else "⚠️ SOME TESTS FAILING"
        status_color = "#28a745" if total_failures == 0 and total_errors == 0 else "#dc3545"
        
        html += f"""
        <div class="status-indicator" style="color: {status_color};">
            <h2>{overall_status}</h2>
        </div>
        
        <div class="summary">
            <div class="metric">
                <h3>{total_tests}</h3>
                <p>Total Tests</p>
            </div>
            <div class="metric passed">
                <h3>{total_passed}</h3>
                <p>Passed ({total_passed/total_tests*100:.1f}%)</p>
            </div>
            <div class="metric failed">
                <h3>{total_failures}</h3>
                <p>Failed</p>
            </div>
            <div class="metric failed">
                <h3>{total_errors}</h3>
                <p>Errors</p>
            </div>
            <div class="metric skipped">
                <h3>{total_skipped}</h3>
                <p>Skipped</p>
            </div>
            <div class="metric">
                <h3>{total_time:.2f}s</h3>
                <p>Total Time</p>
            </div>
        </div>
"""
        
        # Add test suites
        for suite_name, suite_data in results.items():
            if not suite_data:
                continue
                
            tests = suite_data.get('tests', 0)
            failures = suite_data.get('failures', 0)
            errors = suite_data.get('errors', 0)
            passed = tests - failures - errors - suite_data.get('skipped', 0)
            
            html += f"""
        <div class="suite">
            <div class="suite-header">
                📋 {suite_name.upper()} Suite - {tests} tests, {passed} passed, {failures} failed, {errors} errors
            </div>
"""
            
            # Add test cases
            if 'testcases' in suite_data:
                for testcase in suite_data['testcases']:
                    name = testcase.get('name', 'Unknown')
                    status = testcase.get('status', 'unknown')
                    time = testcase.get('time', 0)
                    
                    status_icons = {
                        'passed': '✅',
                        'failed': '❌',
                        'error': '⚠️',
                        'skipped': '⏭️'
                    }
                    
                    icon = status_icons.get(status, '❓')
                    
                    html += f"""
            <div class="test-case {status}">
                {icon} {name} ({time:.3f}s)
"""
                    
                    if status in ['failed', 'error']:
                        error_msg = testcase.get('failure', testcase.get('error', 'Unknown error'))
                        html += f"<br><small>{error_msg[:200]}...</small>"
                    
                    html += "</div>"
            
            html += "</div>"
        
        html += """
    </div>
</body>
</html>
"""
        return html
    
    def save_reports(self, results: Dict):
        """Save both text and HTML reports."""
        # Generate reports
        text_report = self.generate_summary_report(results)
        html_report = self.generate_html_report(results)
        
        # Save text report
        with open(self.results_dir / "test_analysis_report.txt", "w", encoding="utf-8") as f:
            f.write(text_report)
        
        # Save HTML report
        with open(self.results_dir / "test_analysis_report.html", "w", encoding="utf-8") as f:
            f.write(html_report)
        
        print(f"✅ Reports saved:")
        print(f"   📄 Text: {self.results_dir / 'test_analysis_report.txt'}")
        print(f"   🌐 HTML: {self.results_dir / 'test_analysis_report.html'}")
    
    def analyze(self):
        """Run complete analysis and generate reports."""
        print("🔍 Analyzing test results...")
        
        # Load all results
        results = self.load_all_results()
        
        if not results:
            print("❌ No test result files found!")
            print("Make sure you have run tests and have *_test_results.xml files in the tests directory.")
            return
        
        print(f"📁 Found {len(results)} test suite(s)")
        
        # Generate and display summary
        summary = self.generate_summary_report(results)
        print("\n" + summary)
        
        # Save detailed reports
        self.save_reports(results)
        
        return results


def main():
    """Main entry point for the test results analyzer."""
    parser = argparse.ArgumentParser(
        description="Analyze and visualize test results from the MLOps project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_analyzer.py                    # Analyze all results in tests/
  python test_analyzer.py --dir results/    # Analyze results in custom directory
  python test_analyzer.py --format html     # Generate only HTML report
        """
    )
    
    parser.add_argument(
        "--dir",
        default="tests",
        help="Directory containing test result files (default: tests)"
    )
    
    parser.add_argument(
        "--format",
        choices=["text", "html", "both"],
        default="both",
        help="Output format (default: both)"
    )
    
    args = parser.parse_args()
    
    # Create analyzer
    analyzer = TestResultsAnalyzer(args.dir)
    
    # Run analysis
    try:
        results = analyzer.analyze()
        
        if results:
            print(f"\n🎯 Analysis complete! Check the generated reports in {args.dir}/")
            
            # Open HTML report if requested
            if args.format in ["html", "both"]:
                html_path = Path(args.dir) / "test_analysis_report.html"
                print(f"\n💡 To view the HTML report, open: {html_path}")
                print(f"   Or run: start {html_path}")  # Windows
                
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()