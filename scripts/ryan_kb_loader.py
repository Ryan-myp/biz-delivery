"""
RyanKB - 真实知识库加载器
从 /Users/yanping.ma/ryan-personal-knowledge 加载真实文档内容

核心功能:
  1. 按领域加载文档
  2. 全文索引
  3. 关键词检索
  4. 内容摘要提取
"""
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import os


@dataclass
class DocEntry:
    """文档条目"""
    path: str
    title: str
    domain: str
    content: str  # 前500字符摘要
    full_path: Path


class RyanKB:
    """Ryan个人知识库加载器"""

    KB_ROOT = Path('/Users/yanping.ma/ryan-personal-knowledge')
    KNOWLEDGE_DIR = KB_ROOT / 'knowledge'

    # 领域到目录的映射
    DOMAIN_DIRS = {
        'advertising': ['advertising', 'ad-platform-example'],
        'agent': ['agent-ai'],
        'ecommerce': [],  # 通用电商知识
        'finance': [],  # 通用金融知识
        'cloud_native': ['cloud-native', 'kubernetes', 'infra'],
        'devops': ['devops'],
        'data_engineering': ['big-data', 'bigdata', 'kafka', 'elasticsearch'],
        'security': ['security', 'jwt', 'https'],
        'ml_ops': ['ml', 'ai', 'algorithms'],
        'gaming': [],  # 暂无专门目录
        'iot': [],  # 暂无专门目录
        'saas': [],  # 暂无专门目录
        'social': [],  # 暂无专门目录
        'logistics': [],  # 暂无专门目录
        'fullstack': ['fullstack', 'software-engineering'],
    }

    def __init__(self):
        self.docs: Dict[str, DocEntry] = {}
        self.index: Dict[str, List[str]] = {}  # keyword -> [doc_paths]
        self._load_all()

    def _load_all(self):
        """加载所有知识库文档"""
        if not self.KNOWLEDGE_DIR.exists():
            print(f"⚠️ 知识库目录不存在: {self.KNOWLEDGE_DIR}")
            return

        count = 0
        for md_file in self.KNOWLEDGE_DIR.rglob('*.md'):
            try:
                entry = self._load_single(md_file)
                if entry:
                    self.docs[entry.path] = entry
                    self._index_doc(entry)
                    count += 1
            except Exception as e:
                pass  # 跳过损坏的文件

        print(f"📚 知识库加载完成: {count} 篇文档")

    def _load_single(self, path: Path) -> Optional[DocEntry]:
        """加载单个文档"""
        try:
            content = path.read_text(encoding='utf-8', errors='ignore')
            # 提取标题
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else path.stem

            # 确定领域
            domain = self._detect_domain(path)

            # 创建摘要 (前500字符)
            summary = content[:500].replace('\n', ' ').strip()

            return DocEntry(
                path=str(path.relative_to(self.KNOWLEDGE_DIR)),
                title=title,
                domain=domain,
                content=summary,
                full_path=path,
            )
        except:
            return None

    def _detect_domain(self, path: Path) -> str:
        """检测文档领域"""
        rel_path = str(path.relative_to(self.KNOWLEDGE_DIR)).lower()

        # 明确领域匹配
        for domain, dirs in self.DOMAIN_DIRS.items():
            for d in dirs:
                if d and d in rel_path:
                    return domain

        # 内容关键词匹配 (用于没有明确目录的文档)
        content_preview = ""
        try:
            content_preview = path.read_text(errors='ignore')[:2000].lower()
        except:
            pass

        # 广告相关
        if any(k in rel_path or k in content_preview for k in ['ad', 'dsp', '竞价', 'rtb', '广告']):
            return 'advertising'

        # Agent相关
        if any(k in rel_path or k in content_preview for k in ['agent', 'llm', '大模型', 'rag', '工具调用']):
            return 'agent'

        # 金融相关
        if any(k in rel_path or k in content_preview for k in ['支付', '交易', 'finance', ' banking', '风控']):
            return 'finance'

        # 电商相关
        if any(k in rel_path or k in content_preview for k in ['电商', '订单', 'inventory', '秒杀', 'commerce']):
            return 'ecommerce'

        # 安全相关
        if any(k in rel_path or k in content_preview for k in ['security', 'jwt', '加密', '认证', 'auth']):
            return 'security'

        # 数据相关
        if any(k in rel_path or k in content_preview for k in ['kafka', 'elasticsearch', '大数据', '数据仓库']):
            return 'data_engineering'

        # 云原生相关
        if any(k in rel_path or k in content_preview for k in ['kubernetes', 'docker', '容器', 'service mesh', 'istio']):
            return 'cloud_native'

        # ML相关
        if any(k in rel_path or k in content_preview for k in ['ml', '机器学习', '模型', '训练', '推理']):
            return 'ml_ops'

        # DevOps相关
        if any(k in rel_path or k in content_preview for k in ['ci/cd', 'jenkins', 'gitops', '部署']):
            return 'devops'

        return 'fullstack'

    def _index_doc(self, doc: DocEntry):
        """建立关键词索引"""
        # 提取关键词 (简单的分词)
        words = re.findall(r'\w+', doc.content.lower())
        for word in words[:50]:  # 只索引前50个词
            if len(word) > 2:
                if word not in self.index:
                    self.index[word] = []
                if doc.path not in self.index[word]:
                    self.index[word].append(doc.path)

    def search(self, query: str, domain: Optional[str] = None, limit: int = 5) -> List[Dict]:
        """搜索知识库"""
        results = []
        query_words = re.findall(r'\w+', query.lower())

        # 收集相关文档
        doc_scores = {}
        for word in query_words:
            if word in self.index:
                for path in self.index[word]:
                    if path not in doc_scores:
                        doc_scores[path] = 0
                    doc_scores[path] += 1

        # 也搜索标题
        title_index = {}
        for doc in self.docs.values():
            title_lower = doc.title.lower()
            for word in query_words:
                if word in title_lower:
                    if doc.path not in title_index:
                        title_index[doc.path] = 0
                    title_index[doc.path] += 2  # 标题匹配权重更高

        # 合并分数
        for path, score in title_index.items():
            doc_scores[path] = doc_scores.get(path, 0) + score

        # 排序并过滤
        sorted_docs = sorted(doc_scores.items(), key=lambda x: -x[1])
        for path, score in sorted_docs[:limit]:
            doc = self.docs.get(path)
            if doc and (not domain or doc.domain == domain):
                results.append({
                    'path': doc.path,
                    'title': doc.title,
                    'domain': doc.domain,
                    'score': score,
                    'summary': doc.content[:200],
                })

        return results

    def get_domain_docs(self, domain: str, limit: int = 10) -> List[Dict]:
        """获取指定领域的文档"""
        results = []
        for doc in self.docs.values():
            if doc.domain == domain:
                results.append({
                    'path': doc.path,
                    'title': doc.title,
                    'summary': doc.content[:200],
                })
                if len(results) >= limit:
                    break
        return results

    def get_stats(self) -> Dict:
        """获取知识库统计"""
        by_domain = {}
        for doc in self.docs.values():
            d = doc.domain
            by_domain[d] = by_domain.get(d, 0) + 1

        return {
            'total_docs': len(self.docs),
            'by_domain': by_domain,
            'index_size': len(self.index),
        }


# 单例
_kb_instance = None

def get_kb() -> RyanKB:
    """获取知识库单例"""
    global _kb_instance
    if _kb_instance is None:
        _kb_instance = RyanKB()
    return _kb_instance


if __name__ == '__main__':
    kb = get_kb()
    stats = kb.get_stats()
    print(f"知识库统计:")
    print(f"  总文档数: {stats['total_docs']}")
    print(f"  索引大小: {stats['index_size']}")
    print(f"\n按领域分布:")
    for domain, count in sorted(stats['by_domain'].items(), key=lambda x: -x[1])[:10]:
        print(f"  {domain}: {count} 篇")

    # 测试搜索
    print(f"\n搜索 '竞价':")
    results = kb.search('竞价', 'advertising', limit=3)
    for r in results:
        print(f"  - {r['title'][:50]}...")
