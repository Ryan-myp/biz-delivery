"""
Technical Design Skill 实现
职责：根据 PRD 生成技术方案（模板填充）

纯确定性实现，不依赖 LLM
"""

import re
from typing import Any, Dict, List, Optional
from ..base import SkillBase, SkillResult


class TDSkill(SkillBase):
    """技术方案生成 Skill - 模板填充"""
    
    REQUIRED_INPUT = ["prd_content"]
    
    def __init__(self, profile: Optional[Dict[str, Any]] = None):
        super().__init__(profile)
    
    def run(self, input_data: Dict[str, Any]) -> SkillResult:
        """执行技术方案生成"""
        # 验证输入
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
                },
                metadata={
                    "skill": "technical_design",
                    "template": "td.md.j2",
                    "approach": "template_based",
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
        }
        
        # 提取标题
        title_match = re.search(r"^#\s+(.+)", prd_content, re.MULTILINE)
        if title_match:
            info["title"] = title_match.group(1).strip()
        
        # 提取需求
        req_section = re.search(r"##\s*需求描述\s*\n(.*?)(?=##\s|$)", prd_content, re.DOTALL | re.IGNORECASE)
        if req_section:
            lines = [l.strip() for l in req_section.group(1).split('\n') if l.strip()]
            info["requirements"] = lines[:10]  # 最多取 10 条
        
        # 提取 API
        api_section = re.search(r"##\s*接口.*?\n(.*?)(?=##\s|$)", prd_content, re.DOTALL | re.IGNORECASE)
        if api_section:
            apis = re.findall(r"(GET|POST|PUT|DELETE)\s+(/\S+)", api_section.group(1))
            info["apis"] = [{"method": a[0], "path": a[1]} for a in apis[:10]]
        
        # 提取数据模型
        model_section = re.search(r"##\s*数据.*?\n(.*?)(?=##\s|$)", prd_content, re.DOTALL | re.IGNORECASE)
        if model_section:
            models = re.findall(r"###\s*(\w+)", model_section.group(1))
            info["data_models"] = models[:5]
        
        return info
    
    def _get_template(self, language: str) -> str:
        """获取模板"""
        templates = {
            "go": """# 技术方案：{title}

## 1. 架构设计

### 1.1 整体架构
- 架构风格：{style}
- 语言：{language}
- 部署方式：容器化部署

### 1.2 模块划分
{modules}

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

## 4. 核心流程

### 4.1 时序图
```
{sequence_diagram}
```

## 5. 非功能需求

### 5.1 性能
- QPS 目标：{qps_target}
- 延迟要求：{latency_target}

### 5.2 可靠性
- 可用性目标：99.9%
- 容灾方案：{disaster_recovery}

### 5.3 安全性
- 认证方式：JWT/OAuth2
- 权限控制：RBAC

## 6. 部署方案

### 6.1 环境
- 开发环境
- 测试环境
- 生产环境

### 6.2 配置管理
- 环境变量
- 配置文件
""",
            "python": """# 技术方案：{title}

## 1. 架构设计

### 1.1 整体架构
- 架构风格：{style}
- 语言：{language}
- 框架：{framework}

### 1.2 模块划分
{modules}

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

## 4. 核心流程

### 4.1 时序图
```
{sequence_diagram}
```

## 5. 非功能需求

### 5.1 性能
- QPS 目标：{qps_target}
- 延迟要求：{latency_target}

### 5.2 可靠性
- 可用性目标：99.9%
- 容灾方案：{disaster_recovery}

## 6. 部署方案

### 6.1 环境
- 开发环境
- 测试环境
- 生产环境
""",
        }
        
        return templates.get(language, templates["go"])
    
    def _fill_template(self, template: str, info: Dict, profile: Dict) -> str:
        """填充模板"""
        # 基础变量
        replacements = {
            "{title}": info.get("title", "未命名项目"),
            "{language}": profile.get("language", "go"),
            "{style}": profile.get("td_style", "微服务架构"),
            "{modules}": self._format_modules(info),
            "{api_table}": self._format_api_table(info),
            "{request_response}": self._format_request_response(info),
            "{data_models}": self._format_data_models(info),
            "{sequence_diagram}": self._format_sequence_diagram(info),
            "{qps_target}": profile.get("qps_target", "1000"),
            "{latency_target}": profile.get("latency_target", "100ms"),
            "{disaster_recovery}": profile.get("disaster_recovery", "主从切换"),
            "{framework}": profile.get("framework", "Gin/Fiber"),
        }
        
        result = template
        for key, value in replacements.items():
            result = result.replace(key, value)
        
        return result
    
    def _format_modules(self, info: Dict) -> str:
        """格式化模块列表"""
        modules = [
            "- 接入层：API 网关、负载均衡",
            "- 业务层：核心业务逻辑处理",
            "- 数据层：数据库访问、缓存",
            "- 基础设施：日志、监控、告警",
        ]
        return "\n".join(modules)
    
    def _format_api_table(self, info: Dict) -> str:
        """格式化 API 表格"""
        if not info.get("apis"):
            return "| GET | /api/v1/... | 占位 |\n| POST | /api/v1/... | 占位 |"
        
        lines = []
        for api in info["apis"][:5]:
            lines.append(f"| {api['method']} | {api['path']} | 待补充 |")
        return "\n".join(lines) if lines else "| GET | /api/v1/... | 占位 |"
    
    def _format_request_response(self, info: Dict) -> str:
        """格式化请求响应"""
        return """**请求示例：**
```json
{
  "key": "value"
}
```

**响应示例：**
```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```"""
    
    def _format_data_models(self, info: Dict) -> str:
        """格式化数据模型"""
        if not info.get("data_models"):
            return "- Entity: 基础实体\n- DTO: 数据传输对象"
        
        return "\n".join(f"- {m}" for m in info["data_models"][:5])
    
    def _format_sequence_diagram(self, info: Dict) -> str:
        """格式化时序图"""
        return """Client -> API Gateway: Request
API Gateway -> Business Service: Call
Business Service -> Database: Query
Database --> Business Service: Response
Business Service --> API Gateway: Result
API Gateway --> Client: Response"""
    
    def _extract_sections(self, td_content: str) -> List[str]:
        """提取章节"""
        sections = []
        for line in td_content.split('\n'):
            if line.startswith('## '):
                sections.append(line.strip())
        return sections
