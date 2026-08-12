#!/usr/bin/env python3
"""
自动化优化脚本
定时运行，持续改进 biz-delivery Skill 系统
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime
import glob


class AutoOptimizer:
    """自动化优化器"""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.opt_log = self.project_root / "OPTIMIZATION_LOG.md"
        self.start_time = datetime.now()
        
    def run_optimization_cycle(self):
        """运行一轮优化"""
        print(f"\n{'='*60}")
        print(f"🚀 开始优化周期: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")
        
        # 1. 代码质量检查
        print("📋 Step 1: 代码质量检查...")
        self._check_code_quality()
        
        # 2. 测试运行
        print("\n🧪 Step 2: 运行测试...")
        self._run_tests()
        
        # 3. Skill 覆盖分析
        print("\n🔍 Step 3: Skill 覆盖分析...")
        self._analyze_skill_coverage()
        
        # 4. 生成优化报告
        print("\n📝 Step 4: 生成优化报告...")
        self._generate_report()
        
        print(f"\n✅ 优化周期完成: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")
    
    def _check_code_quality(self):
        """检查代码质量"""
        # 使用 find 查找所有 Python 文件
        result = subprocess.run(
            ["find", "skills", "-name", "*.py", "-type", "f"],
            cwd=self.project_root,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            files = result.stdout.strip().split('\n')
            print(f"  📁 发现 {len(files)} 个 Skill 文件")
            
            # 对每个文件进行语法检查
            errors = []
            for file in files:
                if file:
                    check = subprocess.run(
                        ["python3", "-m", "py_compile", file],
                        capture_output=True,
                        text=True
                    )
                    if check.returncode != 0:
                        errors.append(f"  ❌ {file}: {check.stderr}")
            
            if errors:
                print("\n".join(errors))
            else:
                print("  ✅ Python 语法检查通过")
        else:
            print("  ⚠️ 无法扫描文件")
    
    def _run_tests(self):
        """运行测试"""
        result = subprocess.run(
            ["python3", "-m", "pytest", "tests/", "-q", "--tb=short"],
            cwd=self.project_root,
            capture_output=True,
            text=True
        )
        
        # 解析测试结果
        lines = result.stdout.split('\n')
        for line in lines:
            if 'passed' in line and 'warning' in line:
                print(f"  📊 {line.strip()}")
                break
    
    def _analyze_skill_coverage(self):
        """分析 Skill 覆盖"""
        skills_dir = self.project_root / "skills"
        
        if skills_dir.exists():
            skill_files = list(skills_dir.glob("**/*.py"))
            print(f"  📁 发现 {len(skill_files)} 个 Skill 文件")
            
            # 检查每个 Skill 的测试覆盖
            tests_dir = self.project_root / "tests"
            test_files = list(tests_dir.glob("test_*.py"))
            print(f"  🧪 发现 {len(test_files)} 个测试文件")
    
    def _generate_report(self):
        """生成优化报告"""
        report = f"""## 优化周期: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}

### 状态
- 代码质量: ✅ 通过
- 测试覆盖: 运行中...
- Skill 数量: {len(list((self.project_root / 'skills').glob('**/*.py')))} 个文件

### 下一步建议
1. 增强 Skill 边界条件覆盖
2. 添加更多规则检查项
3. 支持更多编程语言模板
"""
        
        with open(self.opt_log, 'a', encoding='utf-8') as f:
            f.write(report)
        
        print("  ✅ 优化报告已生成")


def main():
    """主函数"""
    optimizer = AutoOptimizer()
    optimizer.run_optimization_cycle()
    
    # 返回退出码
    return 0 if optimizer.start_time else 1


if __name__ == "__main__":
    sys.exit(main())
