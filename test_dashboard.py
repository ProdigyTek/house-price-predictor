#!/usr/bin/env python3
"""
Test Dashboard - Real-time Test Results Monitoring

This tool provides a real-time dashboard for monitoring test execution
and results in the House Price Prediction MLOps project.
"""

import time
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
import json


class TestDashboard:
    """Real-time test monitoring dashboard."""
    
    def __init__(self):
        """Initialize the dashboard."""
        self.results_dir = Path("tests")
        self.last_update = {}
        
    def clear_screen(self):
        """Clear the terminal screen."""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def get_file_mtime(self, filepath):
        """Get file modification time."""
        try:
            return os.path.getmtime(filepath)
        except:
            return 0
    
    def check_for_updates(self):
        """Check if any result files have been updated."""
        xml_files = list(self.results_dir.glob("*_test_results.xml"))
        xml_files.extend(list(self.results_dir.glob("test_results.xml")))
        
        updated = False
        for xml_file in xml_files:
            current_mtime = self.get_file_mtime(xml_file)
            if xml_file not in self.last_update or current_mtime > self.last_update[xml_file]:
                self.last_update[xml_file] = current_mtime
                updated = True
        
        return updated
    
    def run_analyzer(self):
        """Run the test analyzer to get latest results."""
        try:
            result = subprocess.run(
                [sys.executable, "test_analyzer.py", "--format", "text"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return result.stdout
            else:
                return f"Error running analyzer: {result.stderr}"
        except Exception as e:
            return f"Error: {e}"
    
    def get_quick_status(self):
        """Get a quick status overview."""
        try:
            # Check for unit test results
            unit_results = self.results_dir / "unit_test_results.xml"
            if unit_results.exists():
                # Quick parse to get basic info
                with open(unit_results, 'r') as f:
                    content = f.read()
                    
                # Extract basic info using string parsing (quick and dirty)
                if 'failures="0"' in content and 'errors="0"' in content:
                    status = "✅ PASSING"
                    color = "GREEN"
                else:
                    status = "❌ FAILING"
                    color = "RED"
                
                # Extract test count
                import re
                tests_match = re.search(r'tests="(\d+)"', content)
                tests = tests_match.group(1) if tests_match else "?"
                
                # Extract time
                time_match = re.search(r'time="([\d.]+)"', content)
                test_time = float(time_match.group(1)) if time_match else 0
                
                return {
                    'status': status,
                    'color': color,
                    'tests': tests,
                    'time': test_time,
                    'last_run': datetime.fromtimestamp(self.get_file_mtime(unit_results))
                }
        except Exception as e:
            pass
        
        return {
            'status': "❓ UNKNOWN",
            'color': "YELLOW",
            'tests': "?",
            'time': 0,
            'last_run': None
        }
    
    def display_dashboard(self):
        """Display the main dashboard."""
        self.clear_screen()
        
        # Header
        print("=" * 80)
        print("🚀 HOUSE PRICE PREDICTION - TEST DASHBOARD")
        print("=" * 80)
        print(f"📅 Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Quick status
        status = self.get_quick_status()
        print("📊 QUICK STATUS")
        print("-" * 40)
        print(f"Status: {status['status']}")
        print(f"Tests: {status['tests']}")
        print(f"Last Run: {status['last_run'].strftime('%H:%M:%S') if status['last_run'] else 'Never'}")
        print(f"Duration: {status['time']:.2f}s")
        print()
        
        # Available commands
        print("🎮 COMMANDS")
        print("-" * 40)
        print("  r  - Run unit tests")
        print("  a  - Run all tests") 
        print("  v  - View detailed analysis")
        print("  h  - Open HTML report")
        print("  l  - View logs")
        print("  q  - Quit dashboard")
        print()
        
        # File status
        print("📁 TEST FILES STATUS")
        print("-" * 40)
        xml_files = list(self.results_dir.glob("*_test_results.xml"))
        if xml_files:
            for xml_file in xml_files:
                mtime = datetime.fromtimestamp(self.get_file_mtime(xml_file))
                print(f"  📄 {xml_file.name} - {mtime.strftime('%H:%M:%S')}")
        else:
            print("  ❌ No test result files found")
        
        print("\n" + "=" * 80)
        print("💡 Dashboard updates automatically. Press 'r' to run tests, 'q' to quit.")
    
    def run_tests(self, mode="unit"):
        """Run tests with the specified mode."""
        print(f"\n🏃 Running {mode} tests...")
        try:
            cmd = [sys.executable, "run_tests.py", "--mode", mode]
            
            # Run in real-time, showing output
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Show output in real-time
            for line in process.stdout:
                print(line, end='')
            
            process.wait()
            
            print(f"\n✅ Tests completed with exit code: {process.returncode}")
            input("Press Enter to continue...")
            
        except Exception as e:
            print(f"❌ Error running tests: {e}")
            input("Press Enter to continue...")
    
    def view_analysis(self):
        """View detailed test analysis."""
        print("\n🔍 Generating detailed analysis...")
        analysis = self.run_analyzer()
        print(analysis)
        input("\nPress Enter to continue...")
    
    def view_logs(self):
        """View test logs."""
        log_file = self.results_dir / "test_results.log"
        if log_file.exists():
            print("\n📋 Recent Test Logs:")
            print("-" * 60)
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    # Show last 20 lines
                    for line in lines[-20:]:
                        print(line.rstrip())
            except Exception as e:
                print(f"Error reading logs: {e}")
        else:
            print("\n❌ No log file found")
        
        input("\nPress Enter to continue...")
    
    def open_html_report(self):
        """Open HTML report in browser."""
        html_file = self.results_dir / "test_analysis_report.html"
        
        if not html_file.exists():
            print("\n🔍 Generating HTML report...")
            self.run_analyzer()
        
        if html_file.exists():
            try:
                import webbrowser
                webbrowser.open(f"file://{html_file.absolute()}")
                print(f"\n🌐 Opened HTML report in browser: {html_file}")
            except Exception as e:
                print(f"\n❌ Could not open browser: {e}")
                print(f"Manually open: {html_file.absolute()}")
        else:
            print("\n❌ HTML report not found")
        
        input("Press Enter to continue...")
    
    def run(self):
        """Run the interactive dashboard."""
        print("🚀 Starting Test Dashboard...")
        time.sleep(1)
        
        while True:
            self.display_dashboard()
            
            try:
                # Non-blocking input with timeout
                import select
                import sys
                
                # For Windows compatibility
                if os.name == 'nt':
                    import msvcrt
                    if msvcrt.kbhit():
                        command = msvcrt.getch().decode('utf-8').lower()
                    else:
                        time.sleep(0.5)
                        continue
                else:
                    # Unix/Linux
                    if select.select([sys.stdin], [], [], 0.5) == ([sys.stdin], [], []):
                        command = sys.stdin.read(1).lower()
                    else:
                        continue
                
                # Process commands
                if command == 'q':
                    print("\n👋 Goodbye!")
                    break
                elif command == 'r':
                    self.run_tests("unit")
                elif command == 'a':
                    self.run_tests("all")
                elif command == 'v':
                    self.view_analysis()
                elif command == 'h':
                    self.open_html_report()
                elif command == 'l':
                    self.view_logs()
                else:
                    # Invalid command, just refresh
                    pass
                    
            except KeyboardInterrupt:
                print("\n\n👋 Dashboard stopped. Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                time.sleep(1)


def main():
    """Main entry point."""
    dashboard = TestDashboard()
    dashboard.run()


if __name__ == "__main__":
    main()