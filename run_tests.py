#!/usr/bin/env python3
"""
Test runner script for the Infonomy server.
This script provides convenient commands for running different types of tests.
"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print('='*60)
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed with exit code {e.returncode}")
        return False
    except FileNotFoundError:
        print(f"❌ Command not found: {cmd[0]}")
        print("Make sure pytest is installed: pip install pytest pytest-asyncio pytest-cov httpx")
        return False


def main():
    parser = argparse.ArgumentParser(description="Run tests for the Infonomy server")
    parser.add_argument(
        "test_type",
        choices=["all", "unit", "integration", "api", "fast", "coverage"],
        help="Type of tests to run"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Run tests in verbose mode"
    )
    parser.add_argument(
        "--stop-on-failure", "-x",
        action="store_true",
        help="Stop on first failure"
    )
    
    args = parser.parse_args()
    
    # Base pytest command
    base_cmd = ["python", "-m", "pytest"]
    
    if args.verbose:
        base_cmd.append("-v")
    
    if args.stop_on_failure:
        base_cmd.append("-x")
    
    # Test type specific commands
    if args.test_type == "all":
        cmd = base_cmd + ["tests/"]
        success = run_command(cmd, "All Tests")
    
    elif args.test_type == "unit":
        cmd = base_cmd + ["-m", "unit", "tests/"]
        success = run_command(cmd, "Unit Tests (Fast)")
    
    elif args.test_type == "integration":
        cmd = base_cmd + ["-m", "integration", "tests/"]
        success = run_command(cmd, "Integration Tests")
    
    elif args.test_type == "api":
        cmd = base_cmd + ["-m", "api", "tests/"]
        success = run_command(cmd, "API Tests")
    
    elif args.test_type == "fast":
        cmd = base_cmd + ["-m", "not slow", "tests/"]
        success = run_command(cmd, "Fast Tests (Excluding Slow Tests)")
    
    elif args.test_type == "coverage":
        cmd = base_cmd + [
            "--cov=infonomy_server",
            "--cov-report=html",
            "--cov-report=term-missing",
            "tests/"
        ]
        success = run_command(cmd, "Tests with Coverage Report")
        if success:
            print("\n📊 Coverage report generated in htmlcov/index.html")
    
    if success:
        print(f"\n🎉 {args.test_type.title()} tests completed successfully!")
        sys.exit(0)
    else:
        print(f"\n💥 {args.test_type.title()} tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()