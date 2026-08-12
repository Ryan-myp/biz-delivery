# 故障排查手册

## 常见问题

### 1. 导入错误

#### 问题: `ModuleNotFoundError: No module named 'scripts'`

**原因:** 当前目录不在 Python 路径中。

**解决方案:**
```bash
# 在项目根目录运行
cd /path/to/biz-delivery
python3 -m pytest tests/
# 或
PYTHONPATH=. python3 scripts/query_evidence.py --query "测试"
```

---

#### 问题: `ImportError: cannot import name 'xxx' from 'scripts.query'`

**原因:** 新模块未正确导出。

**解决方案:**
检查 `scripts/query/__init__.py` 是否包含相应的导入和 `__all__` 导出。

---

### 2. 意图识别问题

#### 问题: 查询意图识别不准确

**可能原因:**
1. 查询文本太短（少于 2 个字符）
2. 查询不包含任何已知意图关键词

**解决方案:**
```python
from scripts.query import extract_intent

# 添加更多意图模式
from scripts.query.intent import INTENT_PATTERNS
INTENT_PATTERNS["custom_intent"] = ["自定义关键词1", "自定义关键词2"]

# 或使用英文关键词
intent, confidence = extract_intent("Who called PlaceBid")
```

---

### 3. 模糊匹配问题

#### 问题: 相似词无法匹配

**可能原因:**
1. 阈值设置过高
2. 查询词与目标词差异过大

**解决方案:**
```python
from scripts.query import fuzzy_match, adaptive_threshold

# 降低阈值
threshold = adaptive_threshold("素材", "creative")
print(f"自适应阈值: {threshold}")

# 使用模糊匹配
result = fuzzy_match("素材", "creative", threshold=0.3)
```

---

### 4. Profile 相关问题

#### 问题: Profile 加载失败

**可能原因:**
1. Profile 文件不存在
2. JSON 格式错误
3. 缺少必需字段

**解决方案:**
```bash
# 验证 Profile 格式
python3 -m json.tool profiles/my-service.json > /dev/null

# 使用 init_profile 重新生成
python3 scripts/init_profile.py --name my-service --repo /path/to/repo
```

---

#### 问题: 查询别名不生效

**可能原因:**
1. Profile 中未配置 `query_aliases`
2. 关键词拼写不匹配

**解决方案:**
```python
# 检查 Profile 配置
import json
with open("profiles/my-service.json") as f:
    profile = json.load(f)
print(profile.get("query_aliases", {}))

# 手动添加别名
profile["query_aliases"]["素材"] = ["creative", "ad_material"]
```

---

### 5. 查询性能问题

#### 问题: 查询响应慢

**可能原因:**
1. IR 数据过大
2. 同义词扩展过多
3. 多路搜索并发不足

**解决方案:**
```python
from scripts.query import run_evidence_query

# 限制返回数量
result = run_evidence_query(query, ir_data, top_k=10)

# 减少搜索源
result = run_evidence_query(query, ir_data, sources=["code", "schema"])

# 使用缓存
result = run_evidence_query(query, ir_data, cache_dir=".cache")
```

---

### 6. Wiki 查询问题

#### 问题: Wiki 搜索结果为空

**可能原因:**
1. Wiki 路径不存在
2. 索引文件缺失
3. 查询与内容不相关

**解决方案:**
```bash
# 检查 Wiki 目录
ls -la knowledge/

# 重建索引
python3 scripts/build_wiki_index.py
```

---

### 7. RRF 融合问题

#### 问题: 融合结果排序不正确

**可能原因:**
1. k 值设置不合理
2. source_type 权重配置错误

**解决方案:**
```python
from scripts.query import rrf_fuse

# 调整 k 值
result = rrf_fuse(candidates, k=40)  # 更激进排名

# 检查权重配置
from scripts.query.rrf_fusion import SOURCE_WEIGHTS
print(SOURCE_WEIGHTS)
```

---

## 调试技巧

### 1. 启用详细日志

```python
import logging
logging.basicConfig(level=logging.DEBUG)

from scripts.query import run_evidence_query
result = run_evidence_query(query="测试", verbose=True)
```

---

### 2. 检查中间结果

```python
from scripts.query import extract_intent, expand_synonyms, search_code

query = "素材审核流程"

# 检查意图
intent, confidence = extract_intent(query)
print(f"Intent: {intent}, Confidence: {confidence}")

# 检查扩展
keywords = expand_synonyms(query)
print(f"Keywords: {keywords[:5]}")

# 检查搜索结果
results = search_code(ir_data, keywords)
print(f"Results: {len(results)} items")
```

---

### 3. 单元测试

```bash
# 运行特定测试
python3 -m pytest tests/test_query_module.py -v

# 运行 E2E 测试
python3 -m pytest tests/test_e2e.py -v

# 运行所有测试
python3 -m pytest tests/ -v
```

---

## 错误代码

| 错误码 | 说明 | 解决方案 |
|--------|------|----------|
| `INTENT_UNKNOWN` | 意图识别失败 | 检查查询文本是否包含关键词 |
| `PROFILE_INVALID` | Profile 格式错误 | 验证 JSON 格式和必需字段 |
| `IR_CACHE_MISSING` | IR 缓存不存在 | 运行 learn 命令生成缓存 |
| `WIKI_PATH_INVALID` | Wiki 路径无效 | 检查路径是否存在 |
| `QUERY_EMPTY` | 查询为空 | 提供有效的查询文本 |
| `FUZZY_THRESHOLD_HIGH` | 模糊匹配阈值过高 | 降低阈值或使用精确匹配 |

---

## 联系方式

如有问题，请参考：
- [README.md](../README.md) — 项目概述
- [QUICKSTART.md](../QUICKSTART.md) — 快速开始
- [extension_guide.md](./extension_guide.md) — 扩展指南
