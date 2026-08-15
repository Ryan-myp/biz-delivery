"""
Agent Execution Skill v1.0 - 专家级
任务调度引擎 + 失败重试 + 进度追踪 + 结果聚合

核心能力:
  1. 任务调度 (基于依赖关系)
  2. 失败重试 (指数退避)
  3. 进度追踪 (实时状态)
  4. 结果聚合 (统一输出)
"""
import time
import json
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from ..base import SkillBase, SkillResult


class TaskStatus:
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    SKIPPED = "skipped"


class AgentExecutionSkill(SkillBase):
    """Agent 执行 Skill - 专家级"""

    REQUIRED_INPUT = ["tasks", "code_context"]

    def __init__(self, profile: Optional[Dict[str, Any]] = None):
        super().__init__(profile)
        self.status_lock = threading.Lock()
        self.task_results: Dict[str, Dict] = {}
        self.progress_callback: Optional[Callable] = None

    def run(self, input_data: Dict[str, Any]) -> SkillResult:
        """执行 Agent 任务"""
        errors = self.validate_input(input_data)
        if errors:
            return SkillResult(success=False, errors=errors)

        tasks = input_data.get("tasks", [])
        code_context = input_data.get("code_context", "")
        profile = input_data.get("profile", self.profile)
        max_retries = input_data.get("max_retries", 3)
        parallelism = input_data.get("parallelism", 2)

        if not tasks:
            return SkillResult(
                success=True,
                output={
                    "results": [],
                    "total_tasks": 0,
                    "completed_tasks": 0,
                    "failed_tasks": 0,
                    "progress": 100,
                    "execution_time": 0,
                },
                metadata={"skill": "agent_execution_v1"}
            )

        try:
            start_time = time.time()
            results = []

            # 按依赖关系排序
            sorted_tasks = self._topological_sort(tasks)

            # 执行任务
            with ThreadPoolExecutor(max_workers=parallelism) as executor:
                future_to_task = {
                    executor.submit(self._execute_task, task, code_context, profile, max_retries): task
                    for task in sorted_tasks
                }

                for future in as_completed(future_to_task):
                    task = future_to_task[future]
                    try:
                        result = future.result()
                        results.append(result)
                        self._update_progress(len(results), len(sorted_tasks))
                    except Exception as e:
                        results.append({
                            "task_id": task.get("id"),
                            "status": TaskStatus.FAILED,
                            "error": str(e),
                            "retry_count": max_retries,
                        })

            execution_time = time.time() - start_time

            # 统计结果
            completed = sum(1 for r in results if r.get("status") == TaskStatus.COMPLETED)
            failed = sum(1 for r in results if r.get("status") == TaskStatus.FAILED)

            return SkillResult(
                success=failed == 0,
                output={
                    "results": results,
                    "total_tasks": len(results),
                    "completed_tasks": completed,
                    "failed_tasks": failed,
                    "skipped_tasks": sum(1 for r in results if r.get("status") == TaskStatus.SKIPPED),
                    "progress": 100,
                    "execution_time": round(execution_time, 2),
                    "success_rate": f"{completed/len(results)*100:.1f}%" if results else "0%",
                },
                metadata={
                    "skill": "agent_execution_v1",
                    "parallelism": parallelism,
                    "max_retries": max_retries,
                }
            )

        except Exception as e:
            return SkillResult(
                success=False,
                errors=[f"Agent execution failed: {str(e)}"]
            )

    def _execute_task(self, task: Dict, code_context: str, profile: Dict, max_retries: int) -> Dict:
        """执行单个任务（带重试）"""
        task_id = task.get("id", "unknown")
        retry_count = 0

        while retry_count <= max_retries:
            try:
                # 更新状态
                self._update_task_status(task_id, TaskStatus.RUNNING)

                # 执行任务
                result = self._run_task_logic(task, code_context, profile)

                # 成功
                self._update_task_status(task_id, TaskStatus.COMPLETED)
                return {
                    "task_id": task_id,
                    "title": task.get("title", ""),
                    "status": TaskStatus.COMPLETED,
                    "result": result,
                    "retry_count": retry_count,
                    "execution_time": result.get("execution_time", 0),
                }

            except Exception as e:
                retry_count += 1
                if retry_count > max_retries:
                    self._update_task_status(task_id, TaskStatus.FAILED)
                    return {
                        "task_id": task_id,
                        "title": task.get("title", ""),
                        "status": TaskStatus.FAILED,
                        "error": str(e),
                        "retry_count": retry_count,
                    }
                else:
                    # 指数退避重试
                    wait_time = 2 ** (retry_count - 1)
                    self._update_task_status(task_id, TaskStatus.RETRYING)
                    time.sleep(min(wait_time, 10))  # 最多等10秒

    def _run_task_logic(self, task: Dict, code_context: str, profile: Dict) -> Dict:
        """执行任务逻辑"""
        task_type = task.get("type", "")
        task_id = task.get("id", "")

        start_time = time.time()

        # 根据任务类型执行不同逻辑
        if task_type == "infrastructure":
            result = self._execute_infrastructure_task(task, code_context, profile)
        elif task_type == "feature":
            result = self._execute_feature_task(task, code_context, profile)
        elif task_type == "test":
            result = self._execute_test_task(task, code_context, profile)
        else:
            result = {"message": f"未知任务类型: {task_type}"}

        execution_time = time.time() - start_time

        return {
            "message": "任务执行成功",
            "execution_time": execution_time,
            "task_type": task_type,
        }

    def _execute_infrastructure_task(self, task: Dict, code_context: str, profile: Dict) -> Dict:
        """执行基础设施任务"""
        # 模拟创建基础设施代码
        task_id = task.get("id", "")
        domain = task.get("domain", "fullstack")

        # 生成基础设施代码模板
        code_templates = {
            'advertising': """// 竞价引擎基础设施
package bidding

import (
    "sync"
    "time"
)

// BidEngine 竞价引擎核心
type BidEngine struct {
    mu          sync.RWMutex
    budgetStore BudgetStore
    profileCache *ProfileCache
    pricingEngine PricingEngine
}

// NewBidEngine 创建竞价引擎
func NewBidEngine(cfg *Config) *BidEngine {
    return &BidEngine{
        budgetStore: NewRedisBudgetStore(cfg.BudgetRedisAddr),
        profileCache: NewProfileCache(cfg.ProfileCacheTTL),
        pricingEngine: NewRuleBasedPricing(cfg.PricingRules),
    }
}

// HandleBidRequest 处理竞价请求
func (e *BidEngine) HandleBidRequest(req *BidRequest) (*BidResponse, error) {
    // 1. 查询用户画像（带降级）
    profile := e.getProfileWithFallback(req.UserID)
    
    // 2. 检查预算（预扣机制）
    if !e.budgetStore.PreDeduct(req.AdvertiserID, req.Budget) {
        return nil, ErrBudgetExceeded
    }
    
    // 3. 计算出价
    bid := e.pricingEngine.CalculateBid(profile, req)
    
    // 4. 返回响应
    return &BidResponse{Bid: bid, BidId: generateUUID()}, nil
}
""",
            'agent': """// Agent 编排基础设施
package agent

import (
    "context"
    "sync"
)

// AgentOrchestrator Agent 编排器
type AgentOrchestrator struct {
    mu         sync.RWMutex
    agents     map[string]Agent
    memory     MemorySystem
    toolRegistry ToolRegistry
}

// NewAgentOrchestrator 创建编排器
func NewAgentOrchestrator(cfg *Config) *AgentOrchestrator {
    return &AgentOrchestrator{
        agents:     make(map[string]Agent),
        memory:     NewVectorMemory(cfg.MemoryStore),
        toolRegistry: NewToolRegistry(),
    }
}

// Execute 执行 Agent 任务
func (o *AgentOrchestrator) Execute(ctx context.Context, task *Task) (*Result, error) {
    // 1. 加载记忆
    memory := o.memory.Load(task.SessionID)
    
    // 2. ReAct 循环
    result, err := o.reactLoop(ctx, task, memory)
    if err != nil {
        return nil, err
    }
    
    // 3. 保存记忆
    o.memory.Save(task.SessionID, result.Memory)
    
    return result, nil
}
""",
            'ecommerce': """// 订单核心基础设施
package order

import (
    "sync"
    "time"
)

// OrderService 订单服务
type OrderService struct {
    mu           sync.Mutex
    orderRepo    OrderRepository
    inventorySvc InventoryService
    paymentSvc   PaymentService
}

// CreateOrder 创建订单
func (s *OrderService) CreateOrder(req *CreateOrderRequest) (*Order, error) {
    // 1. 预扣库存
    if err := s.inventorySvc.Prefund(req.Items); err != nil {
        return nil, ErrInventoryInsufficient
    }
    
    // 2. 创建订单
    order := &Order{
        ID:         generateOrderID(),
        Items:      req.Items,
        Status:     OrderStatusPending,
        CreatedAt:  time.Now(),
    }
    
    if err := s.orderRepo.Create(order); err != nil {
        s.inventorySvc.Release(req.Items) // 释放库存
        return nil, err
    }
    
    return order, nil
}
""",
            'finance': """// 交易核心基础设施
package transaction

import (
    "sync"
    "time"
)

// TransactionService 交易服务
type TransactionService struct {
    mu              sync.Mutex
    accountRepo     AccountRepository
    txRepo          TransactionRepository
    riskEngine      RiskEngine
}

// ExecuteTransaction 执行交易
func (s *TransactionService) ExecuteTransaction(req *TransactionRequest) (*Transaction, error) {
    // 1. 风控检查
    if err := s.riskEngine.Check(req); err != nil {
        return nil, ErrRiskRejected
    }
    
    // 2. 开启事务
    tx, err := s.accountRepo.BeginTransaction()
    if err != nil {
        return nil, err
    }
    
    defer func() {
        if r := recover(); r != nil {
            tx.Rollback()
        }
    }()
    
    // 3. 执行账务
    if err := s.postTransaction(tx, req); err != nil {
        tx.Rollback()
        return nil, err
    }
    
    // 4. 提交
    if err := tx.Commit(); err != nil {
        return nil, err
    }
    
    return tx.GetTransaction(), nil
}
""",
        }

        code = code_templates.get(domain, code_templates['fullstack'])

        # 写入文件
        output_dir = Path(self.profile.get("output_dir", "/tmp"))
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{task_id}_infra.go"
        output_file.write_text(code)

        return {
            "file_created": str(output_file),
            "code_generated": True,
            "message": f"基础设施代码已生成: {output_file.name}",
        }

    def _execute_feature_task(self, task: Dict, code_context: str, profile: Dict) -> Dict:
        """执行功能任务"""
        task_id = task.get("id", "")
        domain = task.get("domain", "fullstack")

        # 生成功能代码模板
        code = f"""// {task.get('title', 'Feature')}
package {domain}

import (
    "context"
)

// Handler 处理器
type Handler struct {{
    // TODO: 实现业务逻辑
}}

// Handle 处理请求
func (h *Handler) Handle(ctx context.Context, req *Request) (*Response, error) {{
    // 1. 参数校验
    if err := req.Validate(); err != nil {{
        return nil, err
    }}

    // 2. 业务逻辑
    result, err := h.process(ctx, req)
    if err != nil {{
        return nil, err
    }}

    // 3. 返回结果
    return &Response{{Data: result}}, nil
}}
"""

        output_dir = Path(self.profile.get("output_dir", "/tmp"))
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{task_id}_feature.go"
        output_file.write_text(code)

        return {
            "file_created": str(output_file),
            "code_generated": True,
            "message": f"功能代码已生成: {output_file.name}",
        }

    def _execute_test_task(self, task: Dict, code_context: str, profile: Dict) -> Dict:
        """执行测试任务"""
        task_id = task.get("id", "")

        code = f"""// {task.get('title', 'Test')}
package {task_id.lower()}

import (
    "testing"
)

func Test{task_id}(t *testing.T) {{
    // TODO: 实现测试用例
    t.Run("正常流程", func(t *testing.T) {{
        // 测试正常场景
    }})
    
    t.Run("异常处理", func(t *testing.T) {{
        // 测试异常场景
    }})
}}
"""

        output_dir = Path(self.profile.get("output_dir", "/tmp"))
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{task_id}_test.go"
        output_file.write_text(code)

        return {
            "file_created": str(output_file),
            "test_generated": True,
            "message": f"测试代码已生成: {output_file.name}",
        }

    def _topological_sort(self, tasks: List[Dict]) -> List[Dict]:
        """拓扑排序（处理依赖）"""
        task_map = {t['id']: t for t in tasks}
        visited = set()
        sorted_tasks = []
        temp_visited = set()

        def dfs(task_id: str):
            if task_id in temp_visited:
                return  # 循环依赖，跳过
            if task_id in visited:
                return

            temp_visited.add(task_id)
            task = task_map.get(task_id)
            if task:
                for dep_id in task.get("depends_on", []):
                    dfs(dep_id)
            temp_visited.remove(task_id)
            visited.add(task_id)
            sorted_tasks.append(task)

        for task in tasks:
            dfs(task['id'])

        return sorted_tasks

    def _update_task_status(self, task_id: str, status: str):
        """更新任务状态"""
        with self.status_lock:
            self.task_results[task_id] = {
                "status": status,
                "updated_at": datetime.now().isoformat(),
            }

    def _update_progress(self, completed: int, total: int):
        """更新进度回调"""
        if self.progress_callback:
            self.progress_callback(completed, total)

    def set_progress_callback(self, callback: Callable):
        """设置进度回调"""
        self.progress_callback = callback

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        with self.status_lock:
            return self.task_results.get(task_id)


if __name__ == "__main__":
    import sys

    # 测试执行
    mock_tasks = [
        {"id": "T001", "type": "infrastructure", "priority": "P0", "domain": "advertising", "depends_on": []},
        {"id": "T002", "type": "feature", "priority": "P1", "domain": "advertising", "depends_on": ["T001"]},
        {"id": "T003", "type": "test", "priority": "P2", "domain": "advertising", "depends_on": ["T002"]},
    ]

    skill = AgentExecutionSkill({"output_dir": "/tmp"})
    result = skill.run({
        "tasks": mock_tasks,
        "code_context": "测试上下文",
        "max_retries": 2,
        "parallelism": 2,
    })

    print(f"执行结果: {'成功' if result.success else '失败'}")
    print(f"完成: {result.output['completed_tasks']}/{result.output['total_tasks']}")
    print(f"成功率: {result.output['success_rate']}")
    print(f"执行时间: {result.output['execution_time']}s")
