# Code Platform 技术方案

> **版本**: v1.0  
> **日期**: 2026-08-15  
> **作者**: biz-delivery Team

---

## 一、项目背景与目标

### 1.1 现状分析

当前 biz-delivery 是一个**命令行驱动**的研发流程自动化系统：

```
PRD → Python脚本 → Markdown报告
```

**核心问题**:
- 操作门槛高，需要命令行技能
- 无法实时查看进度和结果
- 不支持多项目并行管理
- 缺少可视化交互

### 1.2 平台目标

构建 **Code Platform** — 一个 Web 化、可视化的研发流程管理平台：

```
┌─────────────────────────────────────────────────────────────┐
│                    Code Platform (Web UI)                   │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ PRD审查  │  │ 技术方案 │  │ 测试用例 │  │ 代码审查 │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
├─────────────────────────────────────────────────────────────┤
│                    API Gateway (FastAPI)                     │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │PRD Skill │  │ TD Skill │  │ Test Skill│  │Review Skill│  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
├─────────────────────────────────────────────────────────────┤
│              Ryan Knowledge Base (1787篇文档)                │
└─────────────────────────────────────────────────────────────┘
```

**核心价值**:
1. **零门槛**: Web 界面，无需命令行
2. **可视化**: 实时进度、结果展示、历史记录
3. **多项目**: 支持同时管理多个业务线
4. **协作**: 团队共享知识库和最佳实践

---

## 二、系统架构

### 2.1 技术选型

| 层级 | 技术 | 理由 |
|------|------|------|
| **前端** | React + TypeScript | 类型安全，生态成熟 |
| **UI框架** | Ant Design Pro | 企业级组件库 |
| **后端** | Python FastAPI | 高性能异步，与现有 Python 技能无缝集成 |
| **数据库** | SQLite (V1) → PostgreSQL (V2) | 开发期轻量，生产期扩展 |
| **任务队列** | Celery + Redis | 异步任务，支持长耗时操作 |
| **实时通信** | WebSocket | 进度推送，结果实时更新 |

### 2.2 架构分层

```
┌─────────────────────────────────────────────────────────────┐
│                     Layer 4: 前端层                          │
│  React + TypeScript + Ant Design Pro + WebSocket            │
├─────────────────────────────────────────────────────────────┤
│                     Layer 3: API 层                          │
│  FastAPI + Pydantic + JWT 认证                              │
├─────────────────────────────────────────────────────────────┤
│                     Layer 2: 服务层                          │
│  PipelineService + ProjectService + UserService             │
├─────────────────────────────────────────────────────────────┤
│                     Layer 1: 引擎层                          │
│  PRDSkill + TDSkill + TestSkill + ReviewSkill               │
├─────────────────────────────────────────────────────────────┤
│                     Layer 0: 数据层                          │
│  SQLite/PostgreSQL + Redis + 文件系统                        │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 模块划分

```
code-platform/
├── frontend/                 # 前端应用
│   ├── src/
│   │   ├── pages/           # 页面组件
│   │   │   ├── Dashboard/   # 仪表盘
│   │   │   ├── Projects/    # 项目管理
│   │   │   ├── Pipeline/    # 流水线执行
│   │   │   ├── Skills/      # Skill 管理
│   │   │   └── Knowledge/   # 知识库
│   │   ├── components/      # 通用组件
│   │   ├── hooks/           # 自定义 Hooks
│   │   ├── services/        # API 服务
│   │   └── stores/          # 状态管理
│   └── package.json
│
├── backend/                  # 后端应用
│   ├── app/
│   │   ├── api/             # API 路由
│   │   │   ├── v1/
│   │   │   │   ├── projects.py
│   │   │   │   ├── pipelines.py
│   │   │   │   ├── skills.py
│   │   │   │   └── knowledge.py
│   │   ├── core/            # 核心配置
│   │   ├── models/          # 数据模型
│   │   ├── schemas/         # Pydantic Schema
│   │   ├── services/        # 业务服务
│   │   ├── tasks/           # Celery 任务
│   │   └── ws/              # WebSocket 端点
│   ├── requirements.txt
│   └── main.py
│
└── docker/                   # Docker 配置
    ├── Dockerfile.frontend
    ├── Dockerfile.backend
    └── docker-compose.yml
```

---

## 三、核心功能设计

### 3.1 项目管理

**功能**:
- 创建/编辑/删除项目
- 关联代码仓库 (Git URL / 本地路径)
- 配置 Profile (语言、框架、业务域)
- 导入/导出配置

**数据模型**:
```python
class Project(Base):
    id: int
    name: str
    description: str
    language: str  # go/python/java/frontend
    framework: str  # kratos/gin/fastapi/spring-boot
    repo_path: str  # 本地路径或 Git URL
    profile_id: int
    created_at: datetime
    updated_at: datetime
```

### 3.2 流水线执行

**功能**:
- 上传/粘贴 PRD 内容
- 选择执行的 Skill (PRD审查/技术方案/测试用例/代码审查)
- 实时查看执行进度
- 查看执行结果和报告
- 历史记录和对比

**执行流程**:
```
用户提交PRD
    ↓
创建Pipeline记录 (状态: pending)
    ↓
提交Celery异步任务
    ↓
WebSocket推送进度 (running)
    ↓
PRD Skill执行 → 结果存储
    ↓
TD Skill执行 → 结果存储
    ↓
Test Skill执行 → 结果存储
    ↓
更新Pipeline状态 (completed)
    ↓
WebSocket推送完成通知
```

**进度推送示例**:
```json
{
  "pipeline_id": 123,
  "stage": "td",
  "status": "running",
  "progress": 60,
  "message": "正在生成技术方案...",
  "timestamp": "2026-08-15T20:00:00Z"
}
```

### 3.3 Skill 管理

**功能**:
- 查看可用 Skill 列表
- 配置 Skill 参数 (profile、规则开关)
- 查看 Skill 执行历史
- 自定义 Skill 模板

**Skill 注册表**:
```json
{
  "skills": [
    {
      "name": "prd_review",
      "displayName": "PRD审查",
      "description": "专家级PRD审查，85+规则检查",
      "version": "2.0",
      "config": {
        "expert_rules": true,
        "knowledge_base": true,
        "domain_detection": true
      }
    },
    {
      "name": "technical_design",
      "displayName": "技术方案",
      "description": "生成完整技术方案，7章节结构",
      "version": "2.0",
      "config": {
        "include_architecture": true,
        "include_performance": true
      }
    },
    {
      "name": "test_case",
      "displayName": "测试用例",
      "description": "生成场景化测试用例，17+用例",
      "version": "2.0",
      "config": {
        "scenario_coverage": true,
        "boundary_testing": true
      }
    },
    {
      "name": "code_review",
      "displayName": "代码审查",
      "description": "28类安全检查规则",
      "version": "1.0",
      "config": {
        "security_check": true,
        "performance_check": true
      }
    }
  ]
}
```

### 3.4 知识库集成

**功能**:
- 查询 Ryan 知识库 (1787篇文档)
- 搜索结果展示
- 文档预览
- 相关文档推荐

**搜索接口**:
```python
@app.get("/api/v1/knowledge/search")
async def search_knowledge(
    q: str = Query(..., description="搜索关键词"),
    category: str = Query(None, description="分类过滤"),
    limit: int = Query(10, description="结果数量")
):
    results = await knowledge_service.search(q, category, limit)
    return {"results": results, "total": len(results)}
```

### 3.5 报告展示

**PRD审查报告**:
```markdown
# PRD 专家审查报告

## 一、审查概览
| 级别 | 数量 | 说明 |
|------|------|------|
| 🔴 P0 | 0 | 必须修复 |
| 🟡 P1 | 3 | 建议修复 |
| 🔵 P2 | 2 | 可选优化 |

## 二、详细问题
### 🔴 P0 严重问题
(no issues)

### 🟡 P1 重要问题
1. **缺少安全考虑**: PRD 应包含安全考虑
   - 💡 建议: 安全审查应覆盖：认证授权、数据安全、渗透测试、合规要求

## 三、知识库参考
- [DSP架构专家文档](...)
- [Agent模式最佳实践](...)

## 四、执行计划
### 第一阶段: 修复 P0 (阻塞项)
(no items)

### 第二阶段: 处理 P1 (迭代内)
1. **缺少安全考虑** (0.5人天)
```

---

## 四、API 设计

### 4.1 REST API

#### 项目相关
```
GET    /api/v1/projects              # 项目列表
POST   /api/v1/projects              # 创建项目
GET    /api/v1/projects/{id}         # 项目详情
PUT    /api/v1/projects/{id}         # 更新项目
DELETE /api/v1/projects/{id}         # 删除项目
POST   /api/v1/projects/{id}/learn   # 学习代码库
```

#### 流水线相关
```
GET    /api/v1/pipelines             # 流水线列表
POST   /api/v1/pipelines             # 创建流水线
GET    /api/v1/pipelines/{id}        # 流水线详情
POST   /api/v1/pipelines/{id}/run    # 执行流水线
GET    /api/v1/pipelines/{id}/stages # 阶段列表
```

#### Skill 相关
```
GET    /api/v1/skills                # Skill 列表
GET    /api/v1/skills/{name}         # Skill 详情
POST   /api/v1/skills/{name}/run     # 执行 Skill
PUT    /api/v1/skills/{name}/config  # 更新配置
```

#### 知识库相关
```
GET    /api/v1/knowledge/search      # 搜索知识
GET    /api/v1/knowledge/categories  # 分类列表
GET    /api/v1/knowledge/{doc_id}    # 文档详情
```

### 4.2 WebSocket API

```
ws://localhost:8000/ws/pipeline/{id}

消息格式:
{
  "type": "progress" | "result" | "error" | "complete",
  "data": { ... }
}
```

---

## 五、数据库设计

### 5.1 ER 图

```
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│   Project    │       │   Pipeline   │       │   Stage      │
├──────────────┤       ├──────────────┤       ├──────────────┤
│ id (PK)      │───┐   │ id (PK)      │◄──┐   │ id (PK)      │
│ name         │   └──►│ project_id   │   └──►│ pipeline_id  │
│ description  │       │ status       │       │ skill_name   │
│ language     │       │ prd_content  │       │ status       │
│ repo_path    │       │ result       │       │ result       │
│ profile_id   │       │ created_at   │       │ started_at   │
│ created_at   │       └──────────────┘       │ completed_at │
│ updated_at   │                              └──────────────┘
└──────────────┘

┌──────────────┐       ┌──────────────┐
│    Skill     │       │  Knowledge   │
├──────────────┤       ├──────────────┤
│ id (PK)      │       │ id (PK)      │
│ name         │       │ title        │
│ display_name │       │ content      │
│ version      │       │ category     │
│ config       │       │ path         │
│ created_at   │       │ created_at   │
└──────────────┘       └──────────────┘
```

### 5.2 核心表结构

```sql
-- 项目表
CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    language TEXT NOT NULL,
    framework TEXT,
    repo_path TEXT,
    profile JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 流水线表
CREATE TABLE pipelines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    prd_content TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    result JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- 阶段表
CREATE TABLE stages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_id INTEGER NOT NULL,
    skill_name TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    progress INTEGER DEFAULT 0,
    result JSON,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (pipeline_id) REFERENCES pipelines(id)
);

-- Skill配置表
CREATE TABLE skill_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name TEXT NOT NULL UNIQUE,
    config JSON NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 六、前端设计

### 6.1 页面结构

```
Dashboard (仪表盘)
├── 项目概览
├── 最近执行
└── 质量趋势

Projects (项目管理)
├── 项目列表
├── 项目详情
└── 代码库学习

Pipelines (流水线)
├── 执行列表
├── 执行详情
└── 阶段进度

Skills (Skill管理)
├── Skill列表
├── Skill配置
└── 执行历史

Knowledge (知识库)
├── 文档搜索
├── 分类浏览
└── 文档详情
```

### 6.2 核心页面设计

#### Dashboard
- 项目卡片 (名称、语言、最后学习时间)
- 最近执行记录 (状态、耗时、结果)
- 质量评分趋势图
- 待处理 P0 问题统计

#### Pipeline 执行页
- PRD 内容编辑器
- Skill 选择器 (勾选要执行的 Skill)
- 实时进度条 (每个阶段)
- 结果预览面板
- 导出按钮 (Markdown/PDF)

#### Skill 配置页
- Skill 列表
- 参数配置表单
- 规则开关
- 测试执行按钮

---

## 七、部署方案

### 7.1 Docker Compose

```yaml
version: '3.8'

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    volumes:
      - ./profiles:/app/profiles
      - ./knowledge:/app/knowledge
      - ./delivery:/app/delivery
    environment:
      - DATABASE_URL=sqlite:///./platform.db
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis
      - postgres

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    depends_on:
      - backend

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: codeplatform
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: password
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"

volumes:
  pgdata:
```

### 7.2 部署步骤

```bash
# 1. 克隆仓库
git clone <repo-url> && cd code-platform

# 2. 启动服务
docker-compose up -d

# 3. 访问平台
open http://localhost:3000
```

---

## 八、实施计划

### 8.1 Phase 1: MVP (2周)

| 任务 | 工期 | 负责人 |
|------|------|--------|
| 后端 API 框架搭建 | 3天 | Backend |
| 数据库模型设计 | 1天 | Backend |
| 项目 CRUD API | 2天 | Backend |
| Pipeline 执行 API | 3天 | Backend |
| 前端基础框架 | 3天 | Frontend |
| 集成测试 | 2天 | QA |

**MVP 交付**:
- 创建项目
- 上传 PRD
- 执行 Pipeline
- 查看报告

### 8.2 Phase 2: 核心功能 (2周)

| 任务 | 工期 | 负责人 |
|------|------|--------|
| WebSocket 实时进度 | 3天 | Backend |
| Skill 配置管理 | 2天 | Backend |
| 知识库搜索集成 | 3天 | Backend |
| 前端报告展示 | 3天 | Frontend |
| 前端项目/流水线管理 | 3天 | Frontend |

### 8.3 Phase 3: 增强功能 (2周)

| 任务 | 工期 | 负责人 |
|------|------|--------|
| 多用户/权限 | 3天 | Backend |
| 历史记录对比 | 2天 | Frontend |
| 导出 PDF/Markdown | 2天 | Backend |
| 性能优化 | 3天 | All |
| 文档完善 | 2天 | Docs |

---

## 九、风险与应对

| 风险 | 影响 | 应对策略 |
|------|------|----------|
| 前端开发人力不足 | 进度延迟 | 使用 Ant Design Pro 快速开发 |
| WebSocket 连接不稳定 | 用户体验差 | 实现重连机制 + 轮询降级 |
| 知识库查询慢 | 响应延迟 | 添加缓存 + 异步搜索 |
| 并发执行冲突 | 数据不一致 | 加锁机制 + 事务控制 |

---

## 十、成功指标

| 指标 | 目标值 |
|------|--------|
| API 响应时间 P99 | < 500ms |
| Pipeline 执行成功率 | > 95% |
| 前端页面加载时间 | < 2s |
| 用户满意度 | > 4/5 |

---

## 附录

### A. 技术栈版本

```
Python: 3.11+
FastAPI: 0.100+
React: 18+
TypeScript: 5+
Ant Design: 5+
PostgreSQL: 15+
Redis: 7+
Celery: 5+
```

### B. 参考文档

- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [Ant Design Pro 文档](https://pro.ant.design/)
- [Celery 官方文档](https://docs.celeryproject.org/)
