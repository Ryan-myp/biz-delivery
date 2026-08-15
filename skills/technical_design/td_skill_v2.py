"""
Technical Design Skill v2 - 增强版
从 PRD 提取实际内容填充技术方案，而非使用占位符
"""
import re
from typing import Any, Dict, List, Optional
from ..base import SkillBase, SkillResult


class TDSkillV2(SkillBase):
    """技术方案生成 Skill - 增强版，从 PRD 提取实际内容"""

    def __init__(self, profile: Optional[Dict[str, Any]] = None):
        super().__init__(profile)

    def run(self, input_data: Dict[str, Any]) -> SkillResult:
        """执行技术方案生成"""
        errors = self.validate_input(input_data)
        if errors:
            return SkillResult(success=False, errors=errors)

        prd_content = input_data["prd_content"]
        profile = input_data.get("profile", self.profile)

        try:
            # 从 PRD 提取关键信息
            prd_info = self._extract_prd_info(prd_content)

            # 根据语言选择模板
            language = profile.get("language", "go")
            template = self._get_template(language)

            # 填充模板
            td_content = self._fill_template(template, prd_info, profile)

            return SkillResult(
                success=True,
                output={
                    "td_content": td_content,
                    "sections": self._extract_sections(td_content),
                    "language": language,
                    "style": profile.get("td_style", "microservice"),
                    "extracted_info": prd_info,
                },
                metadata={
                    "skill": "technical_design_v2",
                    "template": "td_v2.md.j2",
                    "approach": "prd_based",
                }
            )

        except Exception as e:
            return SkillResult(
                success=False,
                errors=[f"TD generation failed: {str(e)}"]
            )

    def _extract_prd_info(self, prd_content: str) -> Dict[str, Any]:
        """从 PRD 提取关键信息"""
        info = {
            "title": "",
            "requirements": [],
            "apis": [],
            "data_models": [],
            "constraints": [],
            "features": [],
            "tech_stack": [],
        }

        # 提取标题
        title_match = re.search(r"^#\s+(.+)", prd_content, re.MULTILINE)
        if title_match:
            info["title"] = title_match.group(1).strip()

        # 提取功能需求
        for match in re.finditer(r'(?:^|\n)#{3,5}\s*[\d]+\.[\d]+\s*(.+?)(?:\（|\()', prd_content):
            text = match.group(1).strip()
            if len(text) > 3:
                info["features"].append(text)

        # 提取 F1/F2 特性
        for match in re.finditer(r'(?:^|\n)#{4,6}\s*F[\d.]+\s*:\s*(.+)', prd_content):
            info["features"].append(match.group(1).strip())

        # 提取 API（从代码块）
        code_blocks = re.findall(r'```[^\n]*\n(.*?)```', prd_content, re.DOTALL)
        for block in code_blocks[:3]:
            for api_match in re.finditer(r'(GET|POST|PUT|DELETE)\s+(/\S+)', block):
                info["apis"].append({
                    "method": api_match.group(1),
                    "path": api_match.group(2),
                    "desc": "从PRD提取"
                })
            # 提取结构体定义
            for struct_match in re.finditer(r'type\s+(\w+)\s+struct', block):
                info["data_models"].append(struct_match.group(1))
            # 提取 SQL
            for sql_match in re.finditer(r'CREATE\s+TABLE\s+(\w+)', block, re.IGNORECASE):
                info["data_models"].append(sql_match.group(1))

        # 提取技术栈关键词
        tech_keywords = ['go', 'gin', 'fiber', 'echo', 'fastapi', 'flask',
                        'redis', 'kafka', 'mysql', 'postgres', 'mongodb',
                        'docker', 'kubernetes', 'grpc', 'protobuf']
        for kw in tech_keywords:
            if kw in prd_content.lower():
                info["tech_stack"].append(kw)

        # 提取约束
        for match in re.finditer(r'(?:^|\n)[\-*]\s*(.*(?:必须|禁止|不能|应|需).*)', prd_content):
            text = match.group(1).strip()
            if len(text) > 5 and len(text) < 200:
                info["constraints"].append(text)

        return info

    def _get_template(self, language: str) -> str:
        """获取模板"""
        return """# 技术方案：{title}

## 1. 架构设计

### 1.1 整体架构
- 架构风格：{style}
- 语言：{language}
- 框架：{framework}

### 1.2 核心功能模块
{features}

## 2. 接口设计

### 2.1 API 列表
| 方法 | 路径 | 说明 |
|------|------|------|
{api_table}

### 2.2 请求/响应格式
{request_response}

## 3. 数据模型

### 3.1 核心实体
{data_models}

## 4. 技术栈
{tech_stack}

## 5. 核心流程

### 5.1 主要流程
{sequence_diagram}

## 6. 约束与限制
{constraints}

## 7. 部署方案

### 7.1 环境
- 开发环境
- 测试环境
- 生产环境

### 7.2 配置管理
- 环境变量
- 配置文件
"""

    def _fill_template(self, template: str, info: Dict, profile: Dict) -> str:
        """填充模板"""
        # 基础变量
        replacements = {
            "{title}": info.get("title", "未命名项目"),
            "{language}": profile.get("language", "go"),
            "{style}": profile.get("td_style", "模块化架构"),
            "{framework}": self._detect_framework(info),
            "{features}": self._format_features(info),
            "{api_table}": self._format_api_table(info),
            "{request_response}": self._format_request_response(info),
            "{data_models}": self._format_data_models(info),
            "{tech_stack}": self._format_tech_stack(info),
            "{sequence_diagram}": self._format_sequence_diagram(info),
            "{constraints}": self._format_constraints(info),
        }

        result = template
        for key, value in replacements.items():
            result = result.replace(key, value)

        return result

    def _detect_framework(self, info: Dict) -> str:
        """检测框架"""
        tech = info.get("tech_stack", [])
        if "gin" in tech or "fiber" in tech or "echo" in tech:
            return "Gin/Fiber/Echo"
        elif "fastapi" in tech or "flask" in tech:
            return "FastAPI/Flask"
        elif "grpc" in tech:
            return "gRPC"
        return "Go Standard Library"

    def _format_features(self, info: Dict) -> str:
        """格式化功能列表"""
        features = info.get("features", [])[:8]
        if not features:
            return "- 核心业务功能模块"
        lines = []
        for f in features:
            lines.append(f"- {f}")
        return "\n".join(lines)

    def _format_api_table(self, info: Dict) -> str:
        """格式化 API 表格"""
        apis = info.get("apis", [])
        if not apis:
            return "| (从PRD代码块提取) |"
        lines = []
        for api in apis[:5]:
            lines.append(f"| {api['method']} | {api['path']} | {api.get('desc', '')} |")
        return "\n".join(lines)

    def _format_request_response(self, info: Dict) -> str:
        """格式化请求响应示例"""
        models = info.get("data_models", [])
        if models:
            return f"参考 `{models[0]}` 数据结构定义\n\n**请求示例：**\n```json\n{{\n  \"key\": \"value\"\n}}\n```\n\n**响应示例：**\n```json\n{{\n  \"code\": 0,\n  \"message\": \"success\",\n  \"data\": {{}}\n}}\n```"
        return "**请求示例：**\n```json\n{{\n  \"key\": \"value\"\n}}\n```\n\n**响应示例：**\n```json\n{{\n  \"code\": 0,\n  \"message\": \"success\",\n  \"data\": {{}}\n}}\n```"

    def _format_data_models(self, info: Dict) -> str:
        """格式化数据模型"""
        models = info.get("data_models", [])
        if not models:
            return "- Entity: 基础实体\n- DTO: 数据传输对象"
        lines = []
        for m in models[:5]:
            lines.append(f"- **{m}**: 数据模型")
        return "\n".join(lines)

    def _format_tech_stack(self, info: Dict) -> str:
        """格式化技术栈"""
        tech = info.get("tech_stack", [])
        if not tech:
            return "- Go\n- 标准库"
        return "\n".join(f"- {t}" for t in tech[:8])

    def _format_sequence_diagram(self, info: Dict) -> str:
        """格式化时序图"""
        features = info.get("features", [])
        if features:
            first = features[0][:20]
            return f"Client -> Feature({first}): 请求\nFeature -> Database: 数据存储\nDatabase --> Feature: 结果\nFeature --> Client: 响应"
        return "Client -> Service: Request\nService --> Client: Response"

    def _format_constraints(self, info: Dict) -> str:
        """格式化约束"""
        constraints = info.get("constraints", [])
        if not constraints:
            return "- 无特殊约束"
        lines = []
        for c in constraints[:5]:
            lines.append(f"- {c}")
        return "\n".join(lines)

    def _extract_sections(self, content: str) -> List[str]:
        """提取章节"""
        return re.findall(r"^##\s+(.+)", content, re.MULTILINE)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 td_skill_v2.py <prd_file>")
        sys.exit(1)
    with open(sys.argv[1]) as f:
        content = f.read()
    skill = TDSkillV2({"language": "go"})
    result = skill.run({"prd_content": content})
    print(result.output["td_content"])
