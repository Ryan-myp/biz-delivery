#!/usr/bin/env python3
"""
Agent 提示词生成器 — 为不同阶段的 AI Agent 生成精确的执行指令

支持阶段：
1. Setup Agent — 环境准备、依赖安装
2. Implement Agent — 代码实现
3. Test Agent — 测试编写
4. Review Agent — 代码审查
"""

from typing import Dict, List, Optional
from pathlib import Path
import json


# ============================================================================
# Prompt Templates
# ============================================================================

PROMPT_TEMPLATES = {
    "setup": """# 环境准备任务

你是一个 DevOps 工程师。请按以下步骤准备开发环境：

## 任务清单
{tasks}

## 代码仓库信息
- 语言: {language}
- 包管理: {package_manager}
- 当前路径: {repo_path}

## 执行步骤
1. 检查并安装依赖
2. 创建必要的目录结构
3. 配置环境变量
4. 验证环境就绪

## 验收标准
- [ ] 依赖安装成功
- [ ] 目录结构正确
- [ ] 测试命令可执行
""",
    
    "implement": """# 代码实现任务

你是一个资深后端开发工程师。请实现以下功能：

## 功能需求
{requirements}

## 技术方案
{technical_design}

## 代码约束
- 遵循项目现有代码风格
- 添加必要的注释
- 处理异常情况
- 不要修改无关代码

## 输出要求
1. 新生成的文件内容
2. 需要修改的文件及修改内容
3. 编译/构建验证结果

## 验收标准
- [ ] 代码符合项目规范
- [ ] 新增测试用例通过
- [ ] 无编译错误
""",
    
    "test": """# 测试编写任务

你是一个资深 QA 工程师。请为以下功能编写测试：

## 被测功能
{feature_description}

## 测试用例
{test_cases}

## 测试要求
1. 单元测试：覆盖核心业务逻辑
2. 集成测试：验证模块间协作
3. 边界测试：覆盖异常情况

## 输出格式
```markdown
## 测试文件: {test_file}

### 测试用例 1: 
\`\`\`{language}

\`\`\`

**预期结果**: 
""",
    
    "review": """# 代码审查任务

你是一个资深架构师。请审查以下代码变更：

## 变更内容
{changes}

## 审查维度
1. **正确性**: 逻辑是否正确？
2. **安全性**: 是否存在安全隐患？
3. **性能**: 是否有性能问题？
4. **可维护性**: 代码是否易读易维护？
5. **测试覆盖**: 测试是否充分？

## 输出格式
```markdown
## 审查报告

### ✅ 优点
- ...

### ⚠️ 建议改进
- ...

### ❌ 必须修复
- ...

### 评分
- 代码质量: X/10
- 测试覆盖: X/10
- 安全合规: X/10
"""
}


# ============================================================================
# Prompt Generator
# ============================================================================

class AgentPromptGenerator:
    """为不同阶段的 Agent 生成精确的执行指令"""
    
    def __init__(self, profile: dict):
        self.profile = profile
        self.language = profile.get("language", "go")
        self.package_manager = self._detect_package_manager()
    
    def _detect_package_manager(self) -> str:
        """检测包管理器"""
        if self.language == "go":
            return "go mod"
        elif self.language == "python":
            return "pip / poetry"
        elif self.language == "java":
            return "maven / gradle"
        return "unknown"
    
    def generate_setup_prompt(self, repo_path: str) -> str:
        """生成环境准备 Prompt"""
        tasks = """
1. 检查 {language} 开发环境
2. 安装依赖包
3. 创建必要的目录结构
4. 运行基础构建验证
""".format(language=self.language)
        
        return PROMPT_TEMPLATES["setup"].format(
            tasks=tasks,
            language=self.language,
            package_manager=self.package_manager,
            repo_path=repo_path,
        )
    
    def generate_impl_prompt(
        self,
        requirements: str,
        technical_design: str,
        code_context: str = None
    ) -> str:
        """生成代码实现 Prompt"""
        return PROMPT_TEMPLATES["implement"].format(
            requirements=requirements,
            technical_design=technical_design,
        )
    
    def generate_test_prompt(
        self,
        feature_description: str,
        test_cases: List[str],
        test_file: str = None
    ) -> str:
        """生成测试编写 Prompt"""
        cases_text = "\n".join(f"- {tc}" for tc in test_cases)
        
        if test_file is None:
            test_file = f"test_{feature_description[:20].replace(' ', '_')}.{self.language}"
        
        return PROMPT_TEMPLATES["test"].format(
            feature_description=feature_description,
            test_cases=cases_text,
            test_file=test_file,
            language=self.language,
        )
    
    def generate_review_prompt(self, changes: str) -> str:
        """生成代码审查 Prompt"""
        return PROMPT_TEMPLATES["review"].format(changes=changes)
    
    def generate_task_prompt(self, task: dict) -> str:
        """根据任务类型生成专用 Prompt"""
        task_type = task.get("type", "implement")
        
        if task_type == "setup":
            return self.generate_setup_prompt(task.get("repo_path", "."))
        elif task_type == "implement":
            return self.generate_impl_prompt(
                task.get("requirements", ""),
                task.get("technical_design", ""),
                task.get("code_context", ""),
            )
        elif task_type == "test":
            return self.generate_test_prompt(
                task.get("feature", ""),
                task.get("test_cases", []),
                task.get("test_file"),
            )
        elif task_type == "review":
            return self.generate_review_prompt(task.get("changes", ""))
        
        return f"# 任务\n{json.dumps(task, indent=2)}"


# ============================================================================
# Task Decomposer — 任务分解器
# ============================================================================

class TaskDecomposer:
    """将复杂需求分解为可执行的 Agent 任务"""
    
    def __init__(self, profile: dict):
        self.profile = profile
    
    def decompose(self, requirement: str, td_content: str) -> List[Dict]:
        """分解需求为任务列表
        
        Args:
            requirement: 需求描述
            td_content: 技术方案内容
            
        Returns:
            任务列表
        """
        tasks = []
        
        # 1. 解析 TD 提取模块
        modules = self._extract_modules(td_content)
        
        # 2. 为每个模块生成任务
        for module in modules:
            tasks.append({
                "type": "implement",
                "title": f"实现 {module} 模块",
                "requirements": f"实现 {module} 模块的业务逻辑",
                "technical_design": self._extract_module_design(td_content, module),
                "priority": "P0",
                "depends_on": [],
            })
        
        # 3. 添加测试任务
        for module in modules:
            tasks.append({
                "type": "test",
                "title": f"为 {module} 编写测试",
                "feature": module,
                "test_cases": self._generate_test_cases(requirement, module),
                "priority": "P1",
                "depends_on": [f"implement_{module}"],
            })
        
        # 4. 添加代码审查任务
        if modules:
            tasks.append({
                "type": "review",
                "title": "代码审查",
                "changes": f"新增模块: {', '.join(modules)}",
                "priority": "P1",
                "depends_on": [f"test_{m}" for m in modules],
            })
        
        return tasks
    
    def _extract_modules(self, td_content: str) -> List[str]:
        """从 TD 提取模块名"""
        import re
        # 检测 "## 模块: xxx" 或 "### xxx 模块" 模式
        patterns = [
            r'##\s*模块[:：]?\s*(\w+)',
            r'###\s*(\w+)\s*模块',
            r'新增模块\s+([\w\-]+)',
        ]
        modules = set()
        for pattern in patterns:
            matches = re.findall(pattern, td_content)
            modules.update(matches)
        return list(modules)
    
    def _extract_module_design(self, td_content: str, module: str) -> str:
        """提取模块设计细节"""
        import re
        lines = td_content.split('\n')
        in_module = False
        parts = []
        for line in lines:
            stripped = line.strip()
            # 排除三级及以下标题，只匹配 ## 二级标题
            if stripped.startswith('###'):
                if in_module:
                    parts.append(line)
                continue
            # 匹配模块标题（## 模块: X 或 ## X）
            title_match = re.match(r'##\s*(?:模块[:：]\s*)?(.+?)\s*$', stripped)
            if title_match:
                if title_match.group(1).strip() == module:
                    in_module = True
                    continue
                elif in_module:
                    # 遇到下一个 ## 标题，结束
                    break
            elif in_module:
                parts.append(line)
        
        design = '\n'.join(parts).strip()
        if design:
            return design[:1000]
        return f"参考技术方案中关于 {module} 的部分"
    
    def _generate_test_cases(self, requirement: str, module: str) -> List[str]:
        """生成测试用例列表"""
        return [
            f"{module} 正常流程测试",
            f"{module} 异常处理测试",
            f"{module} 边界条件测试",
        ]


# ============================================================================
# Public API
# ============================================================================

def generate_agent_prompt(
    task_type: str,
    profile: dict,
    **kwargs
) -> str:
    """生成 Agent 执行 Prompt
    
    Args:
        task_type: 任务类型 (setup/implement/test/review)
        profile: 业务 Profile
        **kwargs: 任务参数
        
    Returns:
        Agent 执行 Prompt
    """
    generator = AgentPromptGenerator(profile)
    
    if task_type == "setup":
        return generator.generate_setup_prompt(kwargs.get("repo_path", "."))
    elif task_type == "implement":
        return generator.generate_impl_prompt(
            kwargs.get("requirements", ""),
            kwargs.get("technical_design", ""),
            kwargs.get("code_context", ""),
        )
    elif task_type == "test":
        return generator.generate_test_prompt(
            kwargs.get("feature", ""),
            kwargs.get("test_cases", []),
            kwargs.get("test_file"),
        )
    elif task_type == "review":
        return generator.generate_review_prompt(kwargs.get("changes", ""))
    else:
        return f"# 未知任务类型: {task_type}\n{json.dumps(kwargs, indent=2)}"


def decompose_task(
    requirement: str,
    td_content: str,
    profile: dict
) -> List[Dict]:
    """分解需求为可执行任务
    
    Args:
        requirement: 需求描述
        td_content: 技术方案内容
        profile: 业务 Profile
        
    Returns:
        任务列表
    """
    decomposer = TaskDecomposer(profile)
    return decomposer.decompose(requirement, td_content)


if __name__ == "__main__":
    # 测试示例
    sample_profile = {
        "language": "go",
        "package_manager": "go mod",
    }
    
    sample_td = """
## 模块: AdGroup
### 功能描述
广告组管理模块

### 接口设计
- POST /api/v1/adgroups — 创建广告组
- GET /api/v1/adgroups/{id} — 查询广告组

## 模块: Creative
### 功能描述
素材管理模块

### 接口设计
- POST /api/v1/creatives — 创建素材
"""
    
    generator = AgentPromptGenerator(sample_profile)
    
    # 生成实现 Prompt
    impl_prompt = generator.generate_impl_prompt(
        requirements="实现广告组和素材管理功能",
        technical_design=sample_td,
    )
    print("=== 实现 Prompt ===")
    print(impl_prompt[:500])
    
    # 生成测试 Prompt
    test_prompt = generator.generate_test_prompt(
        feature="AdGroup",
        test_cases=["正常创建", "参数校验", "权限检查"],
    )
    print("\n=== 测试 Prompt ===")
    print(test_prompt[:500])
    
    # 任务分解
    decomposer = TaskDecomposer(sample_profile)
    tasks = decomposer.decompose("广告组管理功能", sample_td)
    print(f"\n=== 任务分解 ===")
    print(f"生成 {len(tasks)} 个任务:")
    for task in tasks:
        print(f"  - [{task['priority']}] {task['title']}")
