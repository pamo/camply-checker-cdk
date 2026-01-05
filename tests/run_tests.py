#!/usr/bin/env python3
"""
Test runner for all Lambda tests
"""
import sys
import os
import subprocess

def setup_test_environment():
    """Set up Python test environment"""
    test_env_path = os.path.join(os.path.dirname(__file__), '../test_env')
    
    if not os.path.exists(test_env_path):
        print("Setting up test environment...")
        subprocess.run([sys.executable, '-m', 'venv', test_env_path], check=True)
        
        # Install dependencies
        pip_path = os.path.join(test_env_path, 'bin', 'pip')
        subprocess.run([pip_path, 'install', 'boto3', 'camply==0.33.1', 'pytz'], check=True)
    
    # Activate virtual environment
    activate_script = os.path.join(test_env_path, 'bin', 'activate')
    return test_env_path

def run_all_tests():
    """Run all test suites"""
    print("🧪 Running all Lambda tests...\n")
    
    # Set up environment
    test_env = setup_test_environment()
    python_path = os.path.join(test_env, 'bin', 'python')
    
    # Run unit tests
    print("=" * 50)
    print("UNIT TESTS")
    print("=" * 50)
    unit_result = subprocess.run([
        python_path, 
        os.path.join(os.path.dirname(__file__), 'unit/test_lambda.py')
    ])
    
    print("\n" + "=" * 50)
    print("INTEGRATION TESTS") 
    print("=" * 50)
    integration_result = subprocess.run([
        python_path,
        os.path.join(os.path.dirname(__file__), 'integration/test_lambda_workflow.py')
    ])
    
    # Summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    
    unit_passed = unit_result.returncode == 0
    integration_passed = integration_result.returncode == 0
    
    print(f"Unit Tests: {'✅ PASSED' if unit_passed else '❌ FAILED'}")
    print(f"Integration Tests: {'✅ PASSED' if integration_passed else '❌ FAILED'}")
    
    if unit_passed and integration_passed:
        print("\n🎉 All tests passed! Safe to deploy.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Fix issues before deploying.")
        return 1

if __name__ == "__main__":
    sys.exit(run_all_tests())
