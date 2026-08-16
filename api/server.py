"""
biz-delivery API Server - 基于FastAPI的REST API服务
提供完整的专家系统API接口

核心端点:
  1. POST /api/review - PRD专家审查
  2. POST /api/generate-doc - 文档生成
  3. GET /api/cases - 案例列表
  4. POST /api/quality-check - 质量门禁检查
  5. GET /api/dashboard - 仪表盘数据
  6. GET /api/stats - 系统统计
"""
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.expert_system import SeniorExpertSystem
from scripts.case_learning_engine import CaseLearningEngine, init_sample_cases
from scripts.ai_decision_engine import AIDecisionEngine
from scripts.quality_gate_cli import QualityGateCLI
from scripts.visualization_dashboard import VisualizationDashboard
from scripts.performance_optimizer import get_optimizer
from skills.documentation.doc_skill_v2 import DocumentationSkillV2


# 初始化系统
expert = SeniorExpertSystem()
cases = CaseLearningEngine()
init_sample_cases(cases)
decision_engine = AIDecisionEngine(cases_engine=cases)
gate = QualityGateCLI()
optimizer = get_optimizer()
doc_skill = DocumentationSkillV2({"output_dir": "/tmp/api-docs"})


app = FastAPI(
    title="biz-delivery API",
    description="端到端智能业务交付框架API",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 请求模型
class PRDReviewRequest(BaseModel):
    prd_content: str
    domain: Optional[str] = None


class DocGenerationRequest(BaseModel):
    prd_content: str
    domain: str
    doc_types: List[str] = ["readme"]
    output_dir: str = "/tmp/docs"


class QualityCheckRequest(BaseModel):
    project_path: str
    strict: bool = False


# 响应模型
class ReviewResponse(BaseModel):
    domain: str
    analysis: Dict[str, Any]
    patterns: List[Dict[str, Any]]
    timestamp: str


class CaseResponse(BaseModel):
    case_id: str
    domain: str
    prd_summary: str
    outcome: str
    quality_score: int
    issues_found: List[Dict[str, Any]]
    solutions: List[Dict[str, Any]]
    lessons: List[str]


class StatsResponse(BaseModel):
    total_reviews: int
    total_cases: int
    success_rate: str
    domains_covered: int
    rules_count: int
    cache_stats: Dict[str, Any]


@app.get("/")
async def root():
    return {"message": "biz-delivery API v2.0", "endpoints": [
        "/docs", "/api/review", "/api/generate-doc",
        "/api/cases", "/api/quality-check", "/api/dashboard", "/api/stats"
    ]}


@app.post("/api/review", response_model=ReviewResponse)
async def review_prd(request: PRDReviewRequest):
    """PRD专家审查"""
    try:
        domain = request.domain or expert._detect_domain(request.prd_content)
        result = expert.review(request.prd_content, domain)
        patterns = expert.detect_patterns(request.prd_content, domain)

        return ReviewResponse(
            domain=domain,
            analysis=result.get('analysis', {}),
            patterns=[p.dict() for p in patterns],
            timestamp=datetime.now().isoformat(),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate-doc")
async def generate_doc(request: DocGenerationRequest):
    """文档生成"""
    try:
        result = doc_skill.run({
            "code_path": ".",
            "domain": request.domain,
            "doc_types": request.doc_types,
            "prd_content": request.prd_content,
        })

        if not result.success:
            raise HTTPException(status_code=400, detail=result.errors)

        return {
            "success": True,
            "files_generated": result.output.get('files_generated', []),
            "summary": result.output.get('summary', {}),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/cases")
async def list_cases(domain: Optional[str] = None, limit: int = 10):
    """获取案例列表"""
    cases_list = cases.list_cases(domain)
    return {
        "total": len(cases_list),
        "cases": [vars(c) for c in cases_list[:limit]],
    }


@app.get("/api/cases/{case_id}")
async def get_case(case_id: str):
    """获取单个案例详情"""
    case = cases.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return vars(case)


@app.post("/api/quality-check")
async def quality_check(request: QualityCheckRequest):
    """质量门禁检查"""
    try:
        result = gate.check(request.project_path, request.strict)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dashboard")
async def get_dashboard(days: int = 30):
    """获取仪表盘数据"""
    history = gate.history[-100:] if hasattr(gate, 'history') else []
    dashboard = VisualizationDashboard(history)

    charts = {
        "trend": dashboard.generate_quality_trend_chart(days).model_dump_json(),
        "defects": dashboard.generate_defect_distribution_chart().model_dump_json(),
        "coverage": dashboard.generate_domain_coverage_chart().model_dump_json(),
        "perf": dashboard.generate_performance_gauge().model_dump_json(),
        "compare": dashboard.generate_project_comparison_chart().model_dump_json(),
    }

    return {
        "charts": charts,
        "generated_at": datetime.now().isoformat(),
    }


@app.get("/api/stats", response_model=StatsResponse)
async def get_stats():
    """获取系统统计"""
    case_stats = cases.get_stats()
    opt_stats = optimizer.get_stats()

    return StatsResponse(
        total_reviews=case_stats.get('total_cases', 0),
        total_cases=case_stats.get('total_cases', 0),
        success_rate=case_stats.get('success_rate', '0%'),
        domains_covered=len(expert.kb.knowledge) if hasattr(expert, 'kb') else 15,
        rules_count=275,
        cache_stats=opt_stats,
    )


@app.get("/api/decision")
async def get_decision(prd_content: str, domain: str):
    """AI决策分析"""
    try:
        result = decision_engine.analyze(prd_content, domain)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/plugins")
async def list_plugins(enabled_only: bool = False):
    """获取插件列表"""
    from scripts.plugin_system import get_plugin_manager
    manager = get_plugin_manager()
    return {
        "plugins": manager.list_plugins(enabled_only=enabled_only),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
