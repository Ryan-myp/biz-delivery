#!/usr/bin/env python3
"""
运行完整测试套件
"""

import subprocess
import sys
from pathlib import Path


def run_tests():
    """运行所有测试"""
    test_files = [
        "scripts/test_core_functions.py",
        "scripts/test_e2e.py",
        "scripts/test_workflow.py",
    ]
    
    results = []
    for test_file in test_files:
        if Path(test_file).exists():
            print(f"\n{'='*60}")
            print(f"运行测试: {test_file}")
            print('='*60)
            
            result = subprocess.run(
                ["python", "-m", "pytest", test_file, "-v", "--tb=short"],
                capture_output=True,
                text=True
            )
            
            passed = result.returncode == 0
            results.append((test_file, passed))
            
            if passed:
                print(f"✅ {test_file}: PASS")
            else:
                print(f"❌ {test_file}: FAIL")
                print(result.stdout[-500:])
    
    print(f"\n{'='*60}")
    print("测试结果汇总")
    print('='*60)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    print(f"通过: {passed_count}/{total_count}")
    
    if passed_count == total_count:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print("\n⚠️ 部分测试失败")
        return 1


if __name__ == '__main__':
    sys.exit(run_tests())
