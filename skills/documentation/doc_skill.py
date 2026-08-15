"""
Documentation Skill - 文档生成 Skill
"""
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from ..base import SkillBase, SkillResult


class DocumentationSkill(SkillBase):
    """文档生成 Skill - 自动生成 README、API 文档等"""

    def __init__(self, profile: Optional[Dict[str, Any]] = None):
        super().__init__(profile)

    def run(self, input_data: Dict[str, Any]) -> SkillResult:
        """执行文档生成"""
        errors = self.validate_input(input_data)
        if errors:
            return SkillResult(success=False, errors=errors)

        code_path = input_data.get("code_path", "")
        doc_type = input_data.get("doc_type", "readme")
        max_files = input_data.get("max_files", 30)

        try:
            # 分析项目结构
            analysis = self._analyze_project(code_path, max_files)
            
            # 生成文档
            if doc_type == "readme":
                content = self._generate_readme(analysis)
            elif doc_type == "api":
                content = self._generate_api_docs(analysis)
            elif doc_type == "architecture":
                content = self._generate_architecture_doc(analysis)
            else:
                content = self._generate_readme(analysis)

            return SkillResult(
                success=True,
                output={
                    "doc_type": doc_type,
                    "content": content,
                    "analysis": analysis,
                    "word_count": len(content),
                },
                metadata={
                    "skill": "documentation",
                    "generated_at": "now",
                }
            )

        except Exception as e:
            return SkillResult(
                success=False,
                errors=[f"Documentation generation failed: {str(e)}"]
            )

    def _analyze_project(self, path: str, max_files: int) -> Dict:
        """分析项目结构"""
        path_obj = Path(path)
        
        # 统计文件类型
        ext_counts = {}
        all_files = list(path_obj.rglob('*'))[:max_files * 10]
        
        for f in all_files:
            if f.is_file():
                ext = f.suffix.lower() or '(no extension)'
                ext_counts[ext] = ext_counts.get(ext, 0) + 1
        
        # 检测语言
        languages = {
            '.go': 'Go',
            '.py': 'Python',
            '.java': 'Java',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.rs': 'Rust',
        }
        
        primary_lang = max(ext_counts.items(), key=lambda x: x[1])[0] if ext_counts else '.go'
        language_name = languages.get(primary_lang, primary_lang.upper().lstrip('.'))
        
        # 检测框架关键词
        frameworks = []
        for f in all_files[:max_files]:
            if f.is_file():
                try:
                    content = f.read_text(errors='ignore').lower()
                    fw_keywords = ['gin', 'fiber', 'echo', 'fastapi', 'spring', 'django', 'flask', 'express']
                    for kw in fw_keywords:
                        if kw in content and kw not in frameworks:
                            frameworks.append(kw)
                except:
                    pass
        
        return {
            'path': path,
            'language': language_name,
            'primary_extension': primary_lang,
            'file_counts': ext_counts,
            'total_files': len([f for f in all_files if f.is_file()]),
            'frameworks': frameworks[:3],
        }

    def _generate_readme(self, analysis: Dict) -> str:
        """生成 README"""
        lines = [
            f"# {analysis['path'].split('/')[-1]}",
            "",
            "## Overview",
            "",
            f"- **Language**: {analysis['language']}",
            f"- **Total Files**: {analysis['total_files']}",
        ]
        
        if analysis['frameworks']:
            lines.append(f"- **Frameworks**: {', '.join(analysis['frameworks'])}")
        
        lines.extend([
            "",
            "## Project Structure",
            "",
            "### File Distribution",
            "",
            "| Extension | Count |",
            "|-----------|-------|",
        ])
        
        for ext, count in sorted(analysis['file_counts'].items(), key=lambda x: x[1], reverse=True)[:10]:
            lines.append(f"| {ext} | {count} |")
        
        lines.extend([
            "",
            "## Getting Started",
            "",
            "```bash",
            "# TODO: Add build/run commands",
            "```",
            "",
            "## License",
            "",
            "TODO: Add license information",
        ])
        
        return "\n".join(lines)

    def _generate_api_docs(self, analysis: Dict) -> str:
        """生成 API 文档"""
        return """# API Documentation

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/v1/... | Placeholder |
| POST | /api/v1/... | Placeholder |

## Request/Response

### Example Request
```json
{
  "key": "value"
}
```

### Example Response
```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```
"""

    def _generate_architecture_doc(self, analysis: Dict) -> str:
        """生成架构文档"""
        lines = [
            "# Architecture Documentation",
            "",
            "## Tech Stack",
            "",
            f"- **Language**: {analysis['language']}",
        ]
        
        if analysis['frameworks']:
            lines.append(f"- **Frameworks**: {', '.join(analysis['frameworks'])}")
        
        lines.extend([
            "",
            "## Design Patterns",
            "",
            "- Dependency Injection",
            "- Repository Pattern",
            "- Service Layer",
            "",
            "## Module Structure",
            "",
            "```",
            "project/",
            "├── src/",
            "│   ├── main/",
            "│   │   └── java/",
            "│   └── test/",
            "├── pom.xml",
            "└── README.md",
            "```",
        ])
        
        return "\n".join(lines)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 documentation_skill.py <code_path>")
        sys.exit(1)
    
    skill = DocumentationSkill({})
    result = skill.run({"code_path": sys.argv[1]})
    print(result.output["content"])
