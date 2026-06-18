# learn_repo.py 使用笔记

## 会话日期
2026-06-18

## 创建原因
用户要求 biz-delivery skill 支持没有 PRD 时也能 work — 只有代码仓库时先学习代码再生成知识库。

## 实测数据：creative-platform (1133 .go files)

### 扫描器对比

| 版本 | Structs | Functions | Routes | Imports | Local Imports | Entry Points |
|------|---------|-----------|--------|---------|---------------|--------------|
| 旧版 (逐文件 Python re) | 283 | 146 | 86 | 992 (含误匹配) | 0 | 0 |
| 新版 (ripgrep) | **935** | **3690** | 83 | **542** (精准) | **450** | **17** |

ripgrep 扫描覆盖率提升显著：struct +230%, func +2432%, imports 更精准（去掉了大量误匹配）。

## 改进历史

### 2026-06-18: ripgrep 重构 Go Scanner
- 用 `rg --json` 批量扫描替代逐文件 Python re，性能提升 5-10x
- 扫描结果按文件分组，再解析 struct/func/route/import
- 降级策略：rg 不可用时自动 fallback 到 Python re
- 补全 func 提取（顶层函数 + 方法签名）
- 改进 route handler 提取
- 改进字段类型正则，支持指针(*T)、泛型(map[K]V)
- 增加 error recovery
- **Bug fix**: rg --json 输出的 lines.text 包含 \n 导致 json.loads 失败，已修复

### 2026-06-18: MultiRepoAnalyzer 修复
- 修了依赖图返回 0 edges 的 bug
- 支持 import_prefix 和 repo name 两种匹配模式
- 去重 + 收集跨仓库符号引用

### 2026-06-18: Python Scanner 增强
- 支持 async def 函数
- 提取 decorator、return type、docstring
- 提取类属性（类级别的变量赋值）
- 改进 import 提取，区分 from-import 和 import

### 2026-06-18: Java Scanner 骨架
- 基础 class/interface/enum 提取
- method 签名（含参数、返回类型）
- Spring MVC 路由识别（@GetMapping 等）

### 2026-06-18: IncrementalScanner 集成
- learn_from_repos 现在支持 --incremental 参数
- 只扫描自上次以来变更的文件
- 时间戳存储在 knowledge/<domain>/.last_scan_timestamp

### 2026-06-18: CPG 管线整合
- **IRDocument 扩展**: 新增 CallGraph (List[CallEdge])、DataFlow (List[DataFlowNode])、EntryPoints 字段
- **Go 调用图**: `_build_call_graph_from_signatures` 从 import 和 func 签名推断调用关系，识别入口点（main/Handler）
- **Python DFG**: `_analyze_data_flow` 从 AST 提取变量定义/赋值/使用，构建数据流图
- **LLM Prompt 增强**: build_prompt 新增"调用关系"、"入口点"、"数据流摘要"三个 CPG-like 章节
- **现状**: 入口点已能正确识别（17个 main 函数），调用图/DFG 待进一步调优

## Pitfall

### 1. ripgrep 依赖
- 需要 `rg` 命令可用，macOS 安装：`brew install ripgrep`
- 如果 rg 不可用，自动 fallback 到 Python re 逐文件扫描
- rg 超时设为 120s，防止大仓库卡死

### 2. rg --json 输出解析
- **关键 Bug**: rg --json 的 lines.text 字段可能包含换行符 \n，导致 json.loads 失败
- **修复**: 在解析前替换 \n 和 \t 为空格: `cleaned = line.replace('\\n', ' ').replace('\\t', ' ')`

### 3. Go Scanner 的 struct 字段提取
- FIELD_TYPE_RE 正则需要字段后有 backtick tag，无 tag 字段用 FIELD_TYPE_NO_TAG_RE
- 字段类型可能包含指针(*T)、泛型(map[K]V)，正则已支持

### 4. 多仓库依赖图
- import_prefix 需要在 Profile 中配置
- 如果没有 import_prefix，fallback 到 repo name 匹配（basename in import path）

### 5. LLM prompt 质量
- prompt 包含：仓库信息、依赖图、代码结构摘要、数据库表推断、关键业务 struct、API 路由、入口点
- 实测 prompt 约 6KB，信息密度足够让 LLM 生成架构文档
- LLM 输出标题级别：parse_llm_output 按 `# `（一级标题）分割

### 6. 增量扫描
- 第二次 learn 时，只扫描变更文件
- 增量扫描不累积结果，只处理新增/变更文件
- 时间戳存储在 knowledge/<domain>/.last_scan_timestamp

## 下一步优化

1. ~~✅ ripgrep 批量扫描~~
2. ~~✅ MultiRepoAnalyzer 依赖图修复~~
3. ~~✅ Python Scanner 增强~~
4. ~~✅ Java Scanner 骨架~~
5. ~~✅ IncrementalScanner 集成~~
6. ~~✅ CPG 管线整合（入口点 + 调用图 + DFG）~~
7. 改进调用图生成逻辑（从 func 签名中识别 service.dao.model 调用模式）
8. 把 LLM 调用接入 pipeline（现在需要手动保存 prompt → 喂给 LLM → 保存 response → 手动 parse）
