# query_evidence.py 架构说明

## 当前状态
`query_evidence.py` 是一个 3200+ 行的单一文件，包含多个功能模块。

## 模块划分

### 1. 意图识别 (intent.py)
- `extract_intent()` — 基于关键词匹配的意图识别
- `_INTENT_REVERSE_INDEX` — 反向索引加速匹配

### 2. 多路查询引擎 (multi_path_query.py)
- `smart_search()` — 智能搜索路由
- `enhanced_semantic_search()` — 增强语义搜索
- `cross_field_search()` — 跨字段搜索
- `fuzzy_score()` — 模糊匹配评分

### 3. 证据查询 (evidence_query.py)
- `run_evidence_query()` — 主查询入口
- `expand_synonyms()` — 同义词扩展
- `build_query_tree()` — 构建查询树

### 4. RRF 融合 (rrf_fusion.py)
- `rrf_fusion()` — Reciprocal Rank Fusion 算法
- `combine_results()` — 结果合并

### 5. Wiki 查询 (wiki_query.py)
- `wiki_search()` — Wiki 知识检索
- `compile_knowledge()` — 知识编译

## 重构建议

```
scripts/
├── query_evidence.py          # 保留为公共入口
├── query/
│   ├── intent.py              # 意图识别
│   ├── multi_path_query.py    # 多路查询
│   ├── evidence_query.py      # 证据查询
│   ├── rrf_fusion.py          # RRF 融合
│   └── wiki_query.py          # Wiki 查询
└── ...
```

## 使用示例

```python
from scripts.query_evidence import run_evidence_query

result = run_evidence_query(
    query="广告组批量暂停",
    profile=profile,
    kb_dir="knowledge/creative-platform"
)
```
