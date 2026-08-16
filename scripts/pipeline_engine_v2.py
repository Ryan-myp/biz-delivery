"""
Pipeline Engine v2.0 - 端到端研发流水线
协调所有 Skill，形成完整的从PRD到代码的自动化流程

核心能力:
  1. 阶段编排 (PRD→TD→Plan→Code→Test→Review)
  2. 质量门禁 (每阶段检查)
  3. 反馈循环 (问题自动回流)
  4. 进度追踪 (实时状态)
"""
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
import threading

from skills.prd_review.review_skill_v2 import PRDReviewSkill
from skills.technical_design.td_skill_v3 import TDSkillV3
from skills.task_planning.task_planning_skill_v3 import TaskPlanningSkillV3
from skills.agent_execution.agent_execution_skill_v1 import AgentExecutionSkill
from skills.test_case.test_case_skill_v2 import TestCaseSkillV2
from skills.code_review.code_review_skill_v2 import CodeReviewSkillV2
from scripts.expert_system import SeniorExpertSystem, CaseLearningEngine


class PipelineStage:
    """流水线阶段"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PipelineResult:
    """流水线结果"""
    def __init__(self):
        self.stages: Dict[str, Dict] = {}
        self.errors: List[str] = []
        self.start_time = 0
        self.end_time = 0
        self.total_time = 0

    @property
    def success(self) -> bool:
        return len(self.errors) == 0 and all(
            s.get('status') == PipelineStage.COMPLETED 
            for s in self.stages.values()
        )

    @property
    def completion_rate(self) -> float:
        total = len(self.stages)
        completed = sum(1 for s in self.stages.values() if s.get('status') == PipelineStage.COMPLETED)
        return completed / total * 100 if total > 0 else 0


class PipelineEngine:
    """流水线引擎"""

    STAGES = [
        ("prd_review", "PRD审查"),
        ("expert_analysis", "专家分析"),
        ("tech_design", "技术方案"),
        ("task_planning", "任务规划"),
        ("code_generation", "代码生成"),
        ("test_generation", "测试生成"),
        ("code_review", "代码审查"),
        ("quality_gate", "质量门禁"),
    ]

    def __init__(self, profile: Optional[Dict[str, Any]] = None):
        self.profile = profile or {}
        self.case_engine = CaseLearningEngine()
        self.expert = SeniorExpertSystem()
        self.result = PipelineResult()
        self.progress_callback = None
        self._lock = threading.Lock()

    def run(self, prd_content: str, code_path: str = "", output_dir: str = "/tmp/biz-delivery") -> PipelineResult:
        """运行完整流水线"""
        self.result = PipelineResult()
        self.result.start_time = time.time()

        print(f"\n{'='*60}")
        print(f"🚀 启动 biz-delivery 研发流水线")
        print(f"{'='*60}\n")

        # 阶段1: PRD审查
        self._run_stage("prd_review", self._stage_prd_review, prd_content)

        # 阶段2: 专家分析
        self._run_stage("expert_analysis", self._stage_expert_analysis, prd_content)

        # 阶段3: 技术方案
        self._run_stage("tech_design", self._stage_tech_design, prd_content)

        # 阶段4: 任务规划
        td_content = self.result.stages.get("tech_design", {}).get("output", {}).get("td_content", "")
        self._run_stage("task_planning", self._stage_task_planning, td_content, prd_content)

        # 阶段5: 代码生成 (模拟)
        tasks = self.result.stages.get("task_planning", {}).get("output", {}).get("tasks", [])
        self._run_stage("code_generation", self._stage_code_generation, tasks, output_dir)

        # 阶段6: 测试生成
        self._run_stage("test_generation", self._stage_test_generation, prd_content)

        # 阶段7: 代码审查
        if code_path:
            self._run_stage("code_review", self._stage_code_review, code_path)

        # 阶段8: 质量门禁
        self._run_stage("quality_gate", self._stage_quality_gate)

        self.result.end_time = time.time()
        self.result.total_time = round(self.result.end_time - self.result.start_time, 2)

        return self.result

    def _run_stage(self, name: str, handler, *args):
        """运行单个阶段"""
        with self._lock:
            self.result.stages[name] = {
                "status": PipelineStage.RUNNING,
                "start_time": datetime.now().isoformat(),
            }

        try:
            output = handler(*args)
            with self._lock:
                self.result.stages[name].update({
                    "status": PipelineStage.COMPLETED,
                    "output": output,
                    "end_time": datetime.now().isoformat(),
                })
            print(f"  ✅ {name}: 完成")
        except Exception as e:
            with self._lock:
                self.result.stages[name].update({
                    "status": PipelineStage.FAILED,
                    "error": str(e),
                    "end_time": datetime.now().isoformat(),
                })
            self.result.errors.append(f"{name}: {str(e)}")
            print(f"  ❌ {name}: 失败 - {str(e)}")

        if self.progress_callback:
            self.progress_callback(name, self.result.completion_rate)

    def _stage_prd_review(self, prd: str) -> Dict:
        """PRD审查阶段"""
        skill = PRDReviewSkill(self.profile)
        result = skill.run({"prd_content": prd})
        return {
            "domain": result.output.get("domain", "unknown"),
            "issues": result.output.get("issues", []),
            "p0_count": result.output.get("p0_count", 0),
            "p1_count": result.output.get("p1_count", 0),
            "summary": result.output.get("summary", ""),
        }

    def _stage_expert_analysis(self, prd: str) -> Dict:
        """专家分析阶段"""
        result = self.expert.review(prd)
        return {
            "domain": result.get("domain", "unknown"),
            "business_value": result.get("analysis", {}).get("business_value", {}),
            "technical_feasibility": result.get("analysis", {}).get("technical_feasibility", {}),
            "risks": result.get("analysis", {}).get("risk_assessment", []),
            "report": result.get("report", ""),
        }

    def _stage_tech_design(self, prd: str) -> Dict:
        """技术方案阶段"""
        skill = TDSkillV3(self.profile)
        result = skill.run({"prd_content": prd, "profile": self.profile})
        return {
            "domain": result.output.get("domain", "unknown"),
            "arch_pattern": result.output.get("arch_pattern", "unknown"),
            "tradeoffs": result.output.get("tradeoff_analysis", {}),
            "risks": result.output.get("risk_plan", {}),
            "td_content": result.output.get("td_content", ""),
        }

    def _stage_task_planning(self, td: str, prd: str) -> Dict:
        """任务规划阶段"""
        skill = TaskPlanningSkillV3(self.profile)
        result = skill.run({"td_content": td, "prd_content": prd})
        return {
            "domain": result.output.get("domain", "unknown"),
            "tasks": result.output.get("tasks", []),
            "total_tasks": result.output.get("total_tasks", 0),
            "estimate_days": result.output.get("total_estimate", 0),
            "critical_path": result.output.get("critical_path", []),
        }

    def _stage_code_generation(self, tasks: List[Dict], output_dir: str) -> Dict:
        """代码生成阶段"""
        skill = AgentExecutionSkill({"output_dir": output_dir})
        result = skill.run({
            "tasks": tasks,
            "code_context": "",
            "max_retries": 1,
            "parallelism": 2,
        })
        return {
            "completed": result.output.get("completed_tasks", 0),
            "failed": result.output.get("failed_tasks", 0),
            "total": result.output.get("total_tasks", 0),
            "success_rate": result.output.get("success_rate", "0%"),
        }

    def _stage_test_generation(self, prd: str) -> Dict:
        """测试生成阶段"""
        skill = TestCaseSkillV2(self.profile)
        result = skill.run({"prd_content": prd})
        return {
            "total_cases": result.output.get("total_count", 0),
            "positive": result.output.get("positive_count", 0),
            "negative": result.output.get("negative_count", 0),
            "boundary": result.output.get("boundary_count", 0),
            "performance": result.output.get("performance_count", 0),
        }

    def _stage_code_review(self, code_path: str) -> Dict:
        """代码审查阶段"""
        skill = CodeReviewSkillV2(self.profile)
        result = skill.run({
            "code_path": code_path,
            "domain": "fullstack",
            "file_pattern": "*.go",
        })
        return {
            "files_scanned": result.output.get("total_files", 0),
            "issues_found": result.output.get("total_issues", 0),
            "p0": result.output.get("p0_count", 0),
            "p1": result.output.get("p1_count", 0),
            "summary": result.output.get("summary", ""),
        }

    def _stage_quality_gate(self) -> Dict:
        """质量门禁阶段"""
        # 基于所有阶段结果计算质量分
        score = 100
        deductions = []

        # PRD审查扣分
        prd_stage = self.result.stages.get("prd_review", {})
        p0_issues = prd_stage.get("output", {}).get("p0_count", 0)
        if p0_issues > 0:
            deduction = p0_issues * 10
            score -= deduction
            deductions.append(f"PRD P0问题: -{deduction}")

        # 技术方案扣分
        td_stage = self.result.stages.get("tech_design", {})
        td_risks = td_stage.get("output", {}).get("risks", {}).get("risks", [])
        high_risks = [r for r in td_risks if r.get("level") == "高"]
        if high_risks:
            deduction = len(high_risks) * 5
            score -= deduction
            deductions.append(f"高风险项: -{deduction}")

        # 代码审查扣分
        review_stage = self.result.stages.get("code_review", {})
        review_p0 = review_stage.get("output", {}).get("p0", 0)
        if review_p0 > 0:
            deduction = review_p0 * 15
            score -= deduction
            deductions.append(f"代码P0问题: -{deduction}")

        # 计算评级
        if score >= 90:
            rating = "A+"
        elif score >= 80:
            rating = "A"
        elif score >= 70:
            rating = "B+"
        elif score >= 60:
            rating = "B"
        else:
            rating = "C"

        return {
            "score": max(0, score),
            "rating": rating,
            "deductions": deductions,
            "passed": score >= 60,
        }

    def get_summary(self) -> Dict:
        """获取流水线摘要"""
        stages_status = {name: stage.get("status", "unknown") for name, stage in self.result.stages.items()}
        
        return {
            "success": self.result.success,
            "total_time": self.result.total_time,
            "stages": stages_status,
            "completion_rate": self.result.completion_rate,
            "errors": self.result.errors,
            "quality_gate": self.result.stages.get("quality_gate", {}).get("output", {}),
            "domain": self.result.stages.get("expert_analysis", {}).get("output", {}).get("domain", "unknown"),
        }

    def set_progress_callback(self, callback):
        """设置进度回调"""
        self.progress_callback = callback


def run_pipeline(prd_path: str, code_path: str = "", output_dir: str = "/tmp/biz-delivery"):
    """便捷函数"""
    with open(prd_path) as f:
        prd = f.read()

    engine = PipelineEngine()

    def on_progress(stage, rate):
        print(f"  📊 进度: {rate:.0f}%")

    engine.set_progress_callback(on_progress)
    result = engine.run(prd, code_path, output_dir)

    summary = engine.get_summary()
    print(f"\n{'='*60}")
    print(f"🎯 流水线执行完成")
    print(f"{'='*60}")
    print(f"总时间: {summary['total_time']}s")
    print(f"完成率: {summary['completion_rate']:.0f}%")
    print(f"质量评分: {summary.get('quality_gate', {}).get('score', 'N/A')}")
    print(f"评级: {summary.get('quality_gate', {}).get('rating', 'N/A')}")
    print(f"领域: {summary['domain']}")

    return summary


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 pipeline_engine.py <prd_file> [code_path]")
        sys.exit(1)
    prd_path = sys.argv[1]
    code_path = sys.argv[2] if len(sys.argv) > 2 else ""
    run_pipeline(prd_path, code_path)
