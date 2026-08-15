"""
Ryan Knowledge Bridge - 集成 Ryan Personal Knowledge Base
将个人知识库引入 biz-delivery 系统
"""
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


class RyanKnowledgeBridge:
    """Ryan 个人知识库桥接器"""

    def __init__(self, kb_path: str = None):
        self.kb_path = Path(kb_path) if kb_path else Path('/Users/yanping.ma/ryan-personal-knowledge')
        self.knowledge_index = self._build_index()
        self.skills_index = self._build_skills_index()

    def _build_index(self) -> Dict:
        """构建知识库索引"""
        index = {
            'categories': {},
            'tags': {},
            'total_files': 0,
        }

        knowledge_path = self.kb_path / 'knowledge'
        if not knowledge_path.exists():
            return index

        for md_file in knowledge_path.rglob('*.md'):
            # 提取分类
            try:
                rel_path = md_file.relative_to(knowledge_path)
                parts = rel_path.parts
                category = parts[0] if len(parts) > 0 else 'other'
                
                if category not in index['categories']:
                    index['categories'][category] = []
                index['categories'][category].append({
                    'path': str(md_file),
                    'name': md_file.stem,
                    'rel_path': str(rel_path),
                    'size': md_file.stat().st_size,
                })
                
                index['total_files'] += 1
            except Exception as e:
                continue

        return index

    def _build_skills_index(self) -> Dict:
        """构建 Skills 索引"""
        index = {}
        skills_path = self.kb_path / 'skills'
        
        if not skills_path.exists():
            return index

        for skill_dir in skills_path.iterdir():
            if skill_dir.is_dir():
                skill_md = skill_dir / 'SKILL.md'
                if skill_md.exists():
                    index[skill_dir.name] = {
                        'path': str(skill_md),
                        'exists': True,
                    }
        
        return index

    def search(self, query: str, category: str = None, limit: int = 10) -> List[Dict]:
        """搜索知识库"""
        results = []
        
        # 在指定分类搜索
        search_paths = []
        if category and category in self.knowledge_index['categories']:
            search_paths = [Path(item['path']) for item in self.knowledge_index['categories'][category]]
        else:
            # 全局搜索
            for cat_items in self.knowledge_index['categories'].values():
                search_paths.extend([Path(item['path']) for item in cat_items])
        
        # 简单关键词匹配
        query_lower = query.lower()
        for path in search_paths[:100]:  # 限制搜索范围
            try:
                content = path.read_text(errors='ignore')
                if query_lower in content.lower():
                    # 提取前200字符作为摘要
                    preview = content[:200].replace('\n', ' ')
                    results.append({
                        'path': str(path),
                        'preview': preview,
                        'relevance': self._calculate_relevance(content, query),
                    })
            except:
                continue
        
        # 按相关性排序
        results.sort(key=lambda x: x['relevance'], reverse=True)
        return results[:limit]

    def _calculate_relevance(self, content: str, query: str) -> float:
        """计算相关性分数"""
        content_lower = content.lower()
        query_words = query.lower().split()
        
        score = 0
        for word in query_words:
            if word in content_lower:
                score += content_lower.count(word)
        
        # 标题匹配加分
        title = content.split('\n')[0].lstrip('# ').lower()
        if query.lower() in title:
            score += 10
        
        return score

    def get_category_summary(self, category: str) -> Dict:
        """获取分类摘要"""
        if category not in self.knowledge_index['categories']:
            return {'error': f'Unknown category: {category}'}
        
        items = self.knowledge_index['categories'][category]
        return {
            'category': category,
            'file_count': len(items),
            'total_size': sum(item['size'] for item in items),
            'files': items[:10],  # 返回前10个
        }

    def get_all_categories(self) -> List[str]:
        """获取所有分类"""
        return list(self.knowledge_index['categories'].keys())

    def get_skill_info(self, skill_name: str) -> Dict:
        """获取 Skill 信息"""
        if skill_name not in self.skills_index:
            return {'error': f'Skill not found: {skill_name}'}
        
        skill_path = Path(self.skills_index[skill_name]['path'])
        if not skill_path.exists():
            return {'error': 'Skill file not found'}
        
        content = skill_path.read_text(errors='ignore')
        return {
            'name': skill_name,
            'content_preview': content[:500],
            'content_length': len(content),
        }


def main():
    """命令行入口"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 ryan_knowledge_bridge.py search <query> [category]")
        print("  python3 ryan_knowledge_bridge.py categories")
        print("  python3 ryan_knowledge_bridge.py summary <category>")
        print("  python3 ryan_knowledge_bridge.py skills")
        sys.exit(1)
    
    bridge = RyanKnowledgeBridge()
    command = sys.argv[1]
    
    if command == 'search':
        if len(sys.argv) < 3:
            print("Usage: search <query> [category]")
            sys.exit(1)
        query = sys.argv[2]
        category = sys.argv[3] if len(sys.argv) > 3 else None
        results = bridge.search(query, category)
        print(f"Found {len(results)} results:")
        for r in results:
            print(f"\n[{r['path']}]")
            print(f"  Relevance: {r['relevance']}")
            print(f"  Preview: {r['preview'][:100]}...")
    
    elif command == 'categories':
        categories = bridge.get_all_categories()
        print(f"Available categories ({len(categories)}):")
        for cat in sorted(categories):
            count = len(bridge.knowledge_index['categories'][cat])
            print(f"  {cat}: {count} files")
    
    elif command == 'summary':
        if len(sys.argv) < 3:
            print("Usage: summary <category>")
            sys.exit(1)
        category = sys.argv[2]
        summary = bridge.get_category_summary(category)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    
    elif command == 'skills':
        skills = bridge.get_skill_info
        print(f"Available skills ({len(bridge.skills_index)}):")
        for name in sorted(bridge.skills_index.keys()):
            print(f"  - {name}")
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
