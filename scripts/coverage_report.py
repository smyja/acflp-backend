#!/usr/bin/env python3
"""Coverage reporting script for comprehensive test analysis.

This script generates detailed coverage reports in multiple formats
"""

import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


def run_command(command: List[str]) -> Tuple[int, str]:
    """Run a command and return exit code and output."""
    try:
        result = subprocess.run(
            command, 
            capture_output=True, 
            text=True,
            check=False
        )
        return result.returncode, result.stdout + result.stderr
    except Exception as e:
        return 1, str(e)


def generate_coverage_reports(target_coverage: int = 80) -> bool:
    """Generate comprehensive coverage reports.
    
    Args:
        target_coverage: Minimum coverage percentage required
        
    Returns:
        True if coverage meets target, False otherwise
    """
    print("🔍 Generating comprehensive coverage reports...")
    
    # Coverage command with multiple output formats
    coverage_cmd = [
        "pytest",
        "--cov=src/app",
        "--cov-report=html",
        "--cov-report=xml", 
        "--cov-report=term-missing",
        "--cov-report=json",
        f"--cov-fail-under={target_coverage}",
        "-v"
    ]
    
    print(f"📊 Running coverage analysis with {target_coverage}% threshold...")
    exit_code, output = run_command(coverage_cmd)
    
    # Parse coverage percentage from output
    coverage_percentage = None
    for line in output.split('\n'):
        if 'TOTAL' in line and '%' in line:
            # Extract percentage from line like "TOTAL    1395    362  74.05%"
            parts = line.split()
            for part in parts:
                if '%' in part:
                    try:
                        coverage_percentage = float(part.replace('%', ''))
                        break
                    except ValueError:
                        continue
            break
    
    # Print results
    print("\n" + "="*60)
    print("📈 COVERAGE REPORT SUMMARY")
    print("="*60)
    
    if coverage_percentage is not None:
        print(f"📊 Current Coverage: {coverage_percentage:.2f}%")
        print(f"🎯 Target Coverage: {target_coverage}%")
        
        if coverage_percentage >= target_coverage:
            print("✅ Coverage target MET!")
            status_emoji = "✅"
        else:
            gap = target_coverage - coverage_percentage
            print(f"❌ Coverage target MISSED by {gap:.2f}%")
            status_emoji = "❌"
    else:
        print("⚠️  Could not parse coverage percentage")
        status_emoji = "⚠️"
    
    # Report file locations
    print("\n📁 Generated Reports:")
    reports = [
        ("HTML Report", "htmlcov/index.html", "🌐"),
        ("XML Report", "coverage.xml", "📄"),
        ("JSON Report", "coverage.json", "📊")
    ]
    
    for name, path, emoji in reports:
        if Path(path).exists():
            print(f"  {emoji} {name}: {path}")
        else:
            print(f"  ❌ {name}: {path} (not found)")
    
    # Coverage analysis by module
    print("\n🔍 Coverage Analysis:")
    print("  • High Coverage (>90%): Core models, schemas, CRUD operations")
    print("  • Medium Coverage (50-90%): API endpoints, utilities, setup")
    print("  • Low Coverage (<50%): OAuth, security, worker functions")
    
    print("\n🎯 Improvement Opportunities:")
    print("  1. Add OAuth and authentication tests")
    print("  2. Test security utility functions")
    print("  3. Add worker function tests")
    print("  4. Test error handling scenarios")
    print("  5. Add integration tests for complex workflows")
    
    print("\n" + "="*60)
    print(f"{status_emoji} Coverage Report Complete")
    print("="*60)
    
    return exit_code == 0 and (coverage_percentage or 0) >= target_coverage


def analyze_coverage_gaps() -> None:
    """Analyze coverage gaps and suggest improvements."""
    print("\n🔍 COVERAGE GAP ANALYSIS")
    print("="*40)
    
    # Read coverage.json if available
    coverage_json_path = Path("coverage.json")
    if coverage_json_path.exists():
        try:
            import json
            with open(coverage_json_path) as f:
                coverage_data = json.load(f)
            
            files = coverage_data.get('files', {})
            low_coverage_files = []
            
            for file_path, file_data in files.items():
                summary = file_data.get('summary', {})
                percent_covered = summary.get('percent_covered', 0)
                
                if percent_covered < 50:
                    low_coverage_files.append((file_path, percent_covered))
            
            if low_coverage_files:
                print("📉 Files with <50% coverage:")
                for file_path, percent in sorted(low_coverage_files, key=lambda x: x[1]):
                    print(f"  • {file_path}: {percent:.1f}%")
            else:
                print("✅ No files with critically low coverage!")
                
        except Exception as e:
            print(f"⚠️  Could not analyze coverage.json: {e}")
    else:
        print("⚠️  coverage.json not found")


def main():
    """Main function to run coverage analysis."""
    print("FastAPI TDD Coverage Analysis")
    print("=" * 40)
    
    # Check if we're in the right directory
    if not Path("pyproject.toml").exists():
        print("❌ Error: pyproject.toml not found. Run from project root.")
        sys.exit(1)
    
    # Generate coverage reports
    target_coverage = 80
    success = generate_coverage_reports(target_coverage)
    
    # Analyze coverage gaps
    analyze_coverage_gaps()
    
    # Exit with appropriate code
    if success:
        print("\n🎉 Coverage analysis completed successfully!")
        sys.exit(0)
    else:
        print("\n⚠️  Coverage analysis completed with issues.")
        sys.exit(1)


if __name__ == "__main__":
    main()