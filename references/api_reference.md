# API 参考文档

## query 模块

### 核心函数

#### `extract_intent(query: str) -> Tuple[str, float]`

从查询文本中提取意图和置信度。

**参数:**
- `query`: 查询文本（支持中英文）

**返回:**
- `(intent, confidence)` 元组
  - `intent`: 意图类型，如 `"query"`, `"question"`, `"debug"` 等
  - `confidence`: 置信度 [0, 1]

**示例:**
```python
from scripts.query import extract_intent

intent, confidence = extract_intent("查看素材审核流程")
# → ("query", 0.85)

intent, confidence = extract_intent("为什么竞价失败")
# → ("question", 0.92)
```

---

#### `fuzzy_score(query: str, target: str) -> float`

计算两个字符串的模糊相似度。

**参数:**
- `query`: 查询文本
- `target`: 目标文本

**返回:**
- 相似度分数 [0, 1]

**示例:**
```python
from scripts.query import fuzzy_score

score = fuzzy_score("素材", "素材")
# → 1.0

score = fuzzy_score("creative", "素材")
# → 0.0 (完全不同)
```

---

#### `expand_synonyms(query: str, profile: dict = None) -> List[str]`

同义词扩展，返回扩展后的关键词列表。

**参数:**
- `query`: 查询文本
- `profile`: 可选，业务 Profile（用于读取自定义同义词）

**返回:**
- 扩展后的关键词列表

**示例:**
```python
from scripts.query import expand_synonyms

keywords = expand_synonyms("素材")
# → ["素材", "creative", "ad_material", "广告素材", ...]

profile = {"query_aliases": {"广告组": ["adgroup_custom"]}}
keywords = expand_synonyms("广告组", profile)
# → ["广告组", "adgroup_custom", ...]
```

---

#### `run_evidence_query(query: str, ir_data: dict = None, profile: dict = None, top_k: int = 20) -> Dict`

执行多路证据查询并返回融合结果。

**参数:**
- `query`: 查询文本
- `ir_data`: IR 文档数据
- `profile`: 业务 Profile
- `top_k`: 返回数量

**返回:**
```python
{
    "intent": "query",
    "confidence": 0.85,
    "query": "原始查询",
    "expanded_queries": ["关键词1", "关键词2", ...],
    "results": [...],  # 融合后的搜索结果
    "sources": ["code", "schema", "api_docs"],
    "stats": {
        "total_results": 10,
        "sources_used": 3,
        "intent": "query",
        "confidence": 0.85
    }
}
```

**示例:**
```python
from scripts.query import run_evidence_query

result = run_evidence_query(
    query="素材审核流程",
    ir_data=ir,
    profile=profile,
    top_k=20
)

for r in result["results"]:
    print(f"{r['type']}: {r.get('title', r.get('name', ''))} - {r['score']:.4f}")
```

---

#### `rrf_fuse(candidates: List[List[Dict]], k: int = 60) -> List[Dict]`

RRF（Reciprocal Rank Fusion）融合多个搜索结果列表。

**参数:**
- `candidates`: 多个搜索结果的列表
- `k`: RRF 常数，默认 60

**返回:**
- 融合后的排序结果列表

**示例:**
```python
from scripts.query import rrf_fuse

candidates = [
    [{"name": "A", "score": 0.9}],
    [{"name": "B", "score": 0.8}],
]
result = rrf_fuse(candidates)
# → [{"name": "A", "score": 0.9, "rrf_score": 0.0164}, ...]
```

---

### Wiki 查询函数

#### `query_wiki(query: str, wiki_path: str = None, top_k: int = 5) -> List[Dict]`

查询 Wiki 知识库。

**参数:**
- `query`: 查询文本
- `wiki_path`: 知识库路径
- `top_k`: 返回数量

**返回:**
- 搜索结果列表

---

#### `query_wiki_evidence(query: str, wiki_path: str = None, cache_dir: str = None, graph_data: dict = None, top_k: int = 10) -> List[Dict]`

统一 Wiki 证据查询，融合多种知识源。

---

### 辅助函数

#### `get_intent_patterns() -> Dict[str, List[str]]`

返回所有意图模式定义。

#### `get_builtin_synonyms() -> Dict[str, List[str]]`

返回内置同义词词典。

#### `classify_intent(query: str) -> str`

简单意图分类，返回最可能的意图类型。

---

## init_profile 脚本

### 用法

```bash
# 命令行模式
python3 scripts/init_profile.py --name my-service --repo /path/to/repo --language go

# 交互式模式
python3 scripts/init_profile.py --interactive
```

### 参数

| 参数 | 说明 | 必填 |
|------|------|------|
| `--name`, `-n` | 业务域名名称 | 是 |
| `--repo`, `-r` | 仓库路径 | 是 |
| `--language`, `-l` | 编程语言 (go/python/java) | 否 |
| `--output`, `-o` | 输出文件路径 | 否 |
| `--interactive`, `-i` | 交互式模式 | 否 |

### 输出

生成 `profiles/{name}.json` 文件，包含：
- 基本信息（业务域名、仓库配置）
- 模块列表（自动扫描提取）
- 查询别名（基于目录结构）
- 业务规则（错误码、约束等）
