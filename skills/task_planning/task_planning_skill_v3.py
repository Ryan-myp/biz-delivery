"""
Task Planning Skill v3.0 - 资深专家版
领域自适应任务分解 + 风险驱动优先级 + 依赖智能识别

核心升级:
  1. 领域感知的任务分解
  2. 风险驱动的任务优先级
  3. 依赖关系智能识别
  4. 工期估算
"""
import re
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from ..base import SkillBase, SkillResult


class TaskPlanningSkillV3(SkillBase):
    """任务规划 Skill - 资深专家版"""

    # 领域任务模板
    DOMAIN_TASK_TEMPLATES = {
        'advertising': [
            {"type": "infrastructure", "priority": "P0", "estimate": "2天", "keywords": ["bid", "竞价", "dsp", "ssp"]},
            {"type": "infrastructure", "priority": "P0", "estimate": "1天", "keywords": ["budget", "预算", "频次控制"]},
            {"type": "feature", "priority": "P1", "estimate": "3天", "keywords": ["ranking", "排序", "ecpm"]},
            {"type": "feature", "priority": "P1", "estimate": "2天", "keywords": ["profile", "画像", "用户特征"]},
            {"type": "feature", "priority": "P1", "estimate": "2天", "keywords": ["settlement", "结算", "对账"]},
            {"type": "test", "priority": "P2", "estimate": "1天", "keywords": ["benchmark", "压测", "性能"]},
        ],
        'agent': [
            {"type": "infrastructure", "priority": "P0", "estimate": "2天", "keywords": ["agent", "orchestrator", "manager"]},
            {"type": "infrastructure", "priority": "P0", "estimate": "1天", "keywords": ["memory", "记忆", "context"]},
            {"type": "feature", "priority": "P1", "estimate": "2天", "keywords": ["tool", "工具", "function calling"]},
            {"type": "feature", "priority": "P1", "estimate": "1天", "keywords": ["planner", "规划", "react"]},
            {"type": "feature", "priority": "P1", "estimate": "1天", "keywords": ["guardrail", "安全", "过滤"]},
            {"type": "test", "priority": "P2", "estimate": "1天", "keywords": ["eval", "评估", "benchmark"]},
        ],
        'ecommerce': [
            {"type": "infrastructure", "priority": "P0", "estimate": "2天", "keywords": ["order", "订单", "支付"]},
            {"type": "infrastructure", "priority": "P0", "estimate": "1天", "keywords": ["inventory", "库存", "并发"]},
            {"type": "feature", "priority": "P1", "estimate": "2天", "keywords": ["cart", "购物车", "促销"]},
            {"type": "feature", "priority": "P1", "estimate": "1天", "keywords": ["product", "商品", "SKU"]},
            {"type": "feature", "priority": "P1", "estimate": "1天", "keywords": ["user", "用户", "账户"]},
            {"type": "test", "priority": "P2", "estimate": "1天", "keywords": ["stress", "压测", "并发"]},
        ],
        'finance': [
            {"type": "infrastructure", "priority": "P0", "estimate": "3天", "keywords": ["transaction", "交易", "账务"]},
            {"type": "infrastructure", "priority": "P0", "estimate": "2天", "keywords": ["account", "账户", "余额"]},
            {"type": "feature", "priority": "P1", "estimate": "2天", "keywords": ["risk", "风控", "合规"]},
            {"type": "feature", "priority": "P1", "estimate": "1天", "keywords": ["clearing", "清算", "对账"]},
            {"type": "feature", "priority": "P1", "estimate": "1天", "keywords": ["audit", "审计", "日志"]},
            {"type": "test", "priority": "P2", "estimate": "2天", "keywords": ["security", "安全", "渗透"]},
        ],
        'fullstack': [
            {"type": "infrastructure", "priority": "P0", "estimate": "2天", "keywords": ["db", "数据库", "migration"]},
            {"type": "infrastructure", "priority": "P0", "estimate": "1天", "keywords": ["cache", "缓存", "redis"]},
            {"type": "infrastructure", "priority": "P0", "estimate": "1天", "keywords": ["mq", "消息队列", "kafka"]},
            {"type": "feature", "priority": "P1", "estimate": "2天", "keywords": ["api", "接口", "handler"]},
            {"type": "feature", "priority": "P1", "estimate": "1天", "keywords": ["service", "服务", "业务逻辑"]},
            {"type": "test", "priority": "P2", "estimate": "1天", "keywords": ["test", "测试", "coverage"]},
        ],
    }

    def run(self, input_data: Dict[str, Any]) -> SkillResult:
        """执行任务规划"""
        errors = self.validate_input(input_data)
        if errors:
            return SkillResult(success=False, errors=errors)

        td_content = input_data.get("td_content", "")
        prd_content = input_data.get("prd_content", "")
        profile = input_data.get("profile", self.profile)

        try:
            # 识别领域
            domain = self._detect_domain(td_content, prd_content)

            # 解析 TD
            td_info = self._parse_td(td_content)

            # 生成领域适配任务
            tasks = self._generate_domain_tasks(td_info, domain)

            # 构建依赖关系
            dependencies = self._build_dependencies(tasks)

            # 计算工期
            schedule = self._calculate_schedule(tasks, dependencies)

            return SkillResult(
                success=True,
                output={
                    "tasks": tasks,
                    "total_tasks": len(tasks),
                    "p0_count": sum(1 for t in tasks if t["priority"] == "P0"),
                    "p1_count": sum(1 for t in tasks if t["priority"] == "P1"),
                    "p2_count": sum(1 for t in tasks if t["priority"] == "P2"),
                    "dependencies": dependencies,
                    "schedule": schedule,
                    "domain": domain,
                    "total_estimate": schedule.get("total_days", 0),
                    "critical_path": schedule.get("critical_path", []),
                },
                metadata={
                    "skill": "task_planning_v3",
                    "domain": domain,
                    "approach": "domain_adaptive",
                }
            )

        except Exception as e:
            return SkillResult(
                success=False,
                errors=[f"Task planning failed: {str(e)}"]
            )

    def _detect_domain(self, td_content: str, prd_content: str) -> str:
        """识别领域"""
        content = td_content + " " + prd_content
        scores = {'advertising': 0, 'agent': 0, 'ecommerce': 0, 'finance': 0, 'fullstack': 0}

        # 广告关键词
        for kw in ['竞价', 'RTB', 'DSP', 'SSP', '广告', '出价', '曝光', '归因', 'ROI', 'eCPM']:
            if kw in content:
                scores['advertising'] += 1

        # Agent 关键词
        for kw in ['Agent', 'LLM', 'RAG', 'ReAct', '记忆', 'Tool', 'Planner', 'Multi-Agent']:
            if kw in content:
                scores['agent'] += 1

        # 电商关键词
        for kw in ['订单', '商品', '库存', '支付', '购物车', '促销', '优惠券']:
            if kw in content:
                scores['ecommerce'] += 1

        # 金融关键词
        for kw in ['交易', '账户', '风控', '合规', '清算', '对账']:
            if kw in content:
                scores['finance'] += 1

        max_score = max(scores.values())
        if max_score == 0:
            return 'fullstack'
        return max(scores, key=scores.get)

    def _parse_td(self, td_content: str) -> Dict:
        """解析 TD 内容"""
        info = {
            "title": "",
            "modules": [],
            "apis": [],
            "data_models": [],
            "infrastructure": [],
            "features": [],
        }

        # 提取标题
        title_match = re.search(r"^#\s+(.+)", td_content, re.MULTILINE)
        if title_match:
            info["title"] = title_match.group(1).strip()

        # 提取模块
        modules = re.findall(r"###\s*([\w\s]+?)(?:\n|$)", td_content)
        info["modules"] = [m.strip() for m in modules if len(m.strip()) > 2]

        # 提取 API
        apis = re.findall(r"\|\s*(GET|POST|PUT|DELETE)\s+(/\S+)\s+\|", td_content)
        info["apis"] = apis

        # 提取数据模型
        models = re.findall(r"- \*\*(\w+)\*\*", td_content)
        info["data_models"] = models[:10]

        # 提取基础设施
        infra_keywords = ['Redis', 'Kafka', 'MySQL', 'etcd', 'gRPC', 'Nginx']
        for kw in infra_keywords:
            if kw in td_content:
                info["infrastructure"].append(kw)

        # 提取功能需求
        features = re.findall(r"- (.+?)(?:\n|$)", td_content)
        info["features"] = [f.strip() for f in features if len(f.strip()) > 5][:10]

        return info

    def _generate_domain_tasks(self, td_info: Dict, domain: str) -> List[Dict]:
        """生成领域适配任务"""
        tasks = []
        task_id = 1

        # 获取领域模板
        templates = self.DOMAIN_TASK_TEMPLATES.get(domain, self.DOMAIN_TASK_TEMPLATES['fullstack'])

        # 基础任务
        for template in templates:
            # 检查 TD 中是否有相关关键词
            keywords_found = []
            for kw in template['keywords']:
                if kw.lower() in td_info['title'].lower() or any(kw.lower() in f.lower() for f in td_info.get('features', [])):
                    keywords_found.append(kw)

            # 如果匹配到关键词，添加任务
            if keywords_found or template['type'] == 'infrastructure':
                task = {
                    "id": f"T{task_id:03d}",
                    "title": self._generate_task_title(template['type'], keywords_found, td_info),
                    "description": self._generate_task_description(template['type'], domain),
                    "type": template['type'],
                    "priority": template['priority'],
                    "estimate": template['estimate'],
                    "domain": domain,
                    "keywords": keywords_found,
                    "files_to_create": self._estimate_files(template['type'], domain),
                    "files_to_modify": [],
                    "risk_level": self._assess_risk(template['type'], domain),
                }
                tasks.append(task)
                task_id += 1

        # 根据 TD 中的具体功能生成定制任务
        for feature in td_info.get('features', [])[:5]:
            # 检查是否已覆盖
            already_covered = any(feature[:20] in t['title'] for t in tasks)
            if not already_covered:
                tasks.append({
                    "id": f"T{task_id:03d}",
                    "title": f"功能 - {feature[:30]}...",
                    "description": f"实现功能: {feature}",
                    "type": "feature",
                    "priority": "P1",
                    "estimate": "1天",
                    "domain": domain,
                    "keywords": [],
                    "files_to_create": [f"features/{feature.lower().replace(' ', '_')}.go"],
                    "files_to_modify": [],
                    "risk_level": "中",
                })
                task_id += 1

        # API 任务
        for api in td_info.get('apis', [])[:3]:
            tasks.append({
                "id": f"T{task_id:03d}",
                "title": f"API - {api[0]} {api[1]}",
                "description": f"实现 {api[0]} {api[1]} 接口",
                "type": "feature",
                "priority": "P1",
                "estimate": "0.5天",
                "domain": domain,
                "keywords": ["api"],
                "files_to_create": [f"handlers/{api[1].replace('/', '_')}.go"],
                "files_to_modify": [],
                "risk_level": "低",
            })
            task_id += 1

        # 排序：P0 → P1 → P2
        priority_order = {"P0": 0, "P1": 1, "P2": 2}
        tasks.sort(key=lambda t: priority_order.get(t["priority"], 9))

        return tasks

    def _generate_task_title(self, task_type: str, keywords: List[str], td_info: Dict) -> str:
        """生成任务标题"""
        if task_type == "infrastructure":
            if "bid" in keywords or "竞价" in keywords:
                return "基础设施 - 竞价引擎"
            elif "budget" in keywords or "预算" in keywords:
                return "基础设施 - 预算追踪"
            elif "memory" in keywords or "记忆" in keywords:
                return "基础设施 - 记忆系统"
            elif "order" in keywords or "订单" in keywords:
                return "基础设施 - 订单核心"
            elif "transaction" in keywords or "交易" in keywords:
                return "基础设施 - 交易核心"
            else:
                return "基础设施 - 核心框架"
        return f"功能 - {keywords[0] if keywords else '未分类'}"

    def _generate_task_description(self, task_type: str, domain: str) -> str:
        """生成任务描述"""
        descriptions = {
            'infrastructure': {
                'advertising': "实现竞价引擎基础架构，包括请求处理、画像查询、出价决策",
                'agent': "实现 Agent 编排基础，包括 Orchestrator、Tool Registry、Memory System",
                'ecommerce': "实现订单核心基础设施，包括订单状态机、库存管理、支付网关",
                'finance': "实现交易核心基础设施，包括账务系统、清算引擎、审计日志",
                'fullstack': "实现基础服务框架，包括数据库连接、缓存、消息队列",
            },
            'feature': "实现业务功能模块",
            'test': "编写测试用例并验证功能",
        }
        return descriptions.get(task_type, {}).get(domain, descriptions.get(task_type, "实现功能模块"))

    def _estimate_files(self, task_type: str, domain: str) -> List[str]:
        """估算文件列表"""
        if task_type == "infrastructure":
            return [f"internal/{domain}_infra.go", f"config/{domain}_config.go"]
        elif task_type == "feature":
            return [f"internal/{domain}_service.go", f"internal/{domain}_handler.go"]
        return [f"{domain}_test.go"]

    def _assess_risk(self, task_type: str, domain: str) -> str:
        """评估风险等级"""
        high_risk_infra = {
            'advertising': ['竞价引擎', '预算追踪'],
            'agent': ['Agent编排', '记忆系统'],
            'ecommerce': ['订单核心', '库存管理'],
            'finance': ['交易核心', '账务系统'],
        }

        for pattern in high_risk_infra.get(domain, []):
            if pattern in task_type:
                return "高"
        return "中" if task_type == "infrastructure" else "低"

    def _build_dependencies(self, tasks: List[Dict]) -> Dict[str, List[str]]:
        """构建依赖关系"""
        deps = {}
        infra_tasks = [t for t in tasks if t['type'] == 'infrastructure']
        feature_tasks = [t for t in tasks if t['type'] == 'feature']
        test_tasks = [t for t in tasks if t['type'] == 'test']

        # 基础设施任务之间可能有依赖
        for i, task in enumerate(infra_tasks):
            if i > 0:
                deps[task['id']] = [infra_tasks[i-1]['id']]
            else:
                deps[task['id']] = []

        # 功能任务依赖基础设施
        for task in feature_tasks:
            deps[task['id']] = [t['id'] for t in infra_tasks[:2]]

        # 测试任务依赖功能任务
        for task in test_tasks:
            deps[task['id']] = [t['id'] for t in feature_tasks[:2]]

        return deps

    def _calculate_schedule(self, tasks: List[Dict], deps: Dict) -> Dict:
        """计算执行计划"""
        if not tasks:
            return {"total_days": 0, "critical_path": []}

        # 并行度估算（假设 2 人同时开发）
        parallel_factor = 2

        # 按优先级分组
        p0_tasks = [t for t in tasks if t['priority'] == 'P0']
        p1_tasks = [t for t in tasks if t['priority'] == 'P1']
        p2_tasks = [t for t in tasks if t['priority'] == 'P2']

        # 计算各阶段工期
        def parse_days(estimate: str) -> float:
            match = re.search(r'(\d+\.?\d*)', estimate)
            return float(match.group(1)) if match else 1.0

        p0_days = sum(parse_days(t['estimate']) for t in p0_tasks)
        p1_days = sum(parse_days(t['estimate']) for t in p1_tasks)
        p2_days = sum(parse_days(t['estimate']) for t in p2_tasks)

        # 考虑并行度
        total_days = (p0_days + p1_days + p2_days) / parallel_factor

        # 关键路径
        critical_path = []
        if p0_tasks:
            critical_path.append(f"P0阶段 ({len(p0_tasks)}个任务, {p0_days:.1f}人天)")
        if p1_tasks:
            critical_path.append(f"P1阶段 ({len(p1_tasks)}个任务, {p1_days:.1f}人天)")
        if p2_tasks:
            critical_path.append(f"P2阶段 ({len(p2_tasks)}个任务, {p2_days:.1f}人天)")

        return {
            "total_days": round(total_days, 1),
            "critical_path": critical_path,
            "p0_days": p0_days,
            "p1_days": p1_days,
            "p2_days": p2_days,
            "parallel_factor": parallel_factor,
        }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 task_planning_skill_v3.py <td_file> [prd_file]")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        td_content = f.read()

    prd_content = ""
    if len(sys.argv) > 2:
        with open(sys.argv[2]) as f:
            prd_content = f.read()

    skill = TaskPlanningSkillV3({"language": "go"})
    result = skill.run({"td_content": td_content, "prd_content": prd_content})

    print(f"领域: {result.output['domain']}")
    print(f"总任务: {result.output['total_tasks']} (P0={result.output['p0_count']}, P1={result.output['p1_count']}, P2={result.output['p2_count']})")
    print(f"预估工期: {result.output['total_estimate']} 天")
    print()
    print("任务列表:")
    for task in result.output['tasks'][:10]:
        print(f"  [{task['priority']}] {task['id']} {task['title']} ({task['estimate']})")
    print()
    print("关键路径:")
    for step in result.output['schedule']['critical_path']:
        print(f"  - {step}")
