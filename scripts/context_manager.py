#!/usr/bin/env python3
"""
ContextManager — 上下文管理与 Session 压缩

职责：
  - Token 计算和估算
  - 长对话自动总结/压缩
  - 上下文窗口智能裁剪
  - 跨任务记忆持久化
  - 摘要缓存

设计原则：
  - 不依赖外部库，纯 Python 实现
  - 支持多种模型（通过配置估算 token 率）
  - 可插拔的 summarizer
"""

import json
import math
import re
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


# ──────────────────────────────────────────────
# Token Estimator
# ──────────────────────────────────────────────

class TokenEstimator:
    """Token 估算器（基于字符数估算）"""
    
    # 常见模型的 token 率（字符/token）
    RATES = {
        "agnes": 3.5,      # Agnes 系列
        "gpt-4": 3.0,      # GPT-4
        "gpt-3.5": 4.0,    # GPT-3.5
        "claude": 3.2,     # Claude
        "default": 3.5,
    }
    
    @classmethod
    def estimate(cls, text: str, model: str = "default") -> int:
        """估算文本的 token 数"""
        if not text:
            return 0
        rate = cls.RATES.get(model, cls.RATES["default"])
        return max(1, len(text) // rate)
    
    @classmethod
    def count_messages(cls, messages: List[Dict], model: str = "default") -> int:
        """估算消息列表的 token 总数"""
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            total += cls.estimate(content, model)
            # 系统提示额外开销
            if msg.get("role") == "system":
                total += 10  # 系统消息固定开销
        return total
    
    @classmethod
    def truncate_to_budget(cls, text: str, budget_tokens: int, model: str = "default") -> str:
        """将文本截断到预算范围内"""
        current = cls.estimate(text, model)
        if current <= budget_tokens:
            return text
        
        # 按行截断
        lines = text.split('\n')
        result = []
        tokens_used = 0
        for line in lines:
            line_tokens = cls.estimate(line, model)
            if tokens_used + line_tokens > budget_tokens:
                # 部分保留
                remaining = budget_tokens - tokens_used
                chars = int(remaining * 3.5)  # 反向估算
                result.append(line[:chars] + "...")
                break
            result.append(line)
            tokens_used += line_tokens
        return '\n'.join(result)


# ──────────────────────────────────────────────
# Summary Generator
# ──────────────────────────────────────────────

class SummaryGenerator:
    """对话摘要生成器"""
    
    SUMMARIZE_PROMPT = """你是一个对话摘要专家。请将以下对话压缩为关键信息摘要，保留：
1. 核心需求和问题
2. 技术方案要点
3. 关键决策
4. 待办事项

只输出摘要，不要解释。

【对话历史】
{history}

【摘要】"""
    
    @classmethod
    def summarize(cls, messages: List[Dict], max_tokens: int = 500, model: str = "default") -> str:
        """
        生成交谈摘要
        
        Args:
            messages: 消息列表
            max_tokens: 摘要最大 token 数
            model: 模型名称
            
        Returns:
            摘要文本
        """
        if len(messages) <= 4:
            return ""  # 太短不需要摘要
        
        # 提取用户和助手的关键消息
        key_messages = []
        for msg in messages[-8:]:  # 最近 8 条
            if msg.get("role") in ("user", "assistant"):
                content = msg.get("content", "")[:500]  # 限制每条长度
                key_messages.append(f"{msg['role']}: {content}")
        
        history = "\n".join(key_messages)
        
        # 返回结构化摘要（不调用 LLM，避免循环依赖）
        return cls._extract_summary(history, max_tokens)
    
    @classmethod
    def _extract_summary(cls, history: str, max_tokens: int) -> str:
        """从历史中提取关键信息作为摘要"""
        # 简单规则提取
        lines = history.split('\n')
        summary_parts = []
        
        # 提取用户消息（通常是需求）
        for line in lines:
            if line.startswith("user:"):
                content = line[5:].strip()
                if len(content) > 20:
                    summary_parts.append(f"用户需求: {content[:200]}")
            elif line.startswith("assistant:") and len(summary_parts) < 3:
                content = line[10:].strip()
                # 只保留关键决策
                if any(kw in content.lower() for kw in ["决定", "方案", "设计", "实现", "建议"]):
                    summary_parts.append(f"AI建议: {content[:150]}")
        
        if not summary_parts:
            #  fallback: 取第一条用户消息
            for line in lines:
                if line.startswith("user:"):
                    summary_parts.append(f"需求: {line[5:].strip()[:200]}")
                    break
        
        result = "\n".join(summary_parts)[:max_tokens * 4]  # 粗略转换
        return result or "无摘要"


# ──────────────────────────────────────────────
# Memory System
# ──────────────────────────────────────────────

@dataclass
class MemoryEntry:
    """记忆条目"""
    id: str
    type: str  # "preference", "fact", "decision", "context"
    content: str
    tags: List[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    confidence: float = 1.0
    task_id: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type,
            "content": self.content,
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "confidence": self.confidence,
            "task_id": self.task_id,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'MemoryEntry':
        return cls(**data)


class MemorySystem:
    """跨任务记忆系统"""
    
    def __init__(self, storage_path: str = "/tmp/biz-delivery/memory.json"):
        self.storage_path = Path(storage_path)
        self.memories: List[MemoryEntry] = []
        self._load()
    
    def _load(self):
        """加载记忆"""
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text())
                self.memories = [MemoryEntry.from_dict(m) for m in data.get("memories", [])]
            except:
                self.memories = []
    
    def _save(self):
        """保存记忆"""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"memories": [m.to_dict() for m in self.memories]}
        self.storage_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    
    def add(self, mem_type: str, content: str, tags: List[str] = None, 
            task_id: str = "", confidence: float = 1.0) -> MemoryEntry:
        """添加记忆"""
        entry = MemoryEntry(
            id=f"mem_{int(time.time()*1000)}",
            type=mem_type,
            content=content,
            tags=tags or [],
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            confidence=confidence,
            task_id=task_id,
        )
        self.memories.append(entry)
        self._save()
        return entry
    
    def search(self, query: str, tags: List[str] = None, limit: int = 10) -> List[MemoryEntry]:
        """搜索记忆"""
        results = []
        query_lower = query.lower()
        
        for mem in self.memories:
            score = 0
            if query_lower in mem.content.lower():
                score += 10
            if tags:
                for tag in tags:
                    if tag in mem.tags:
                        score += 5
                    if tag in mem.content.lower():
                        score += 3
            
            if score > 0:
                results.append((score, mem))
        
        # 按分数排序
        results.sort(key=lambda x: -x[0])
        return [m for _, m in results[:limit]]
    
    def get_by_task(self, task_id: str) -> List[MemoryEntry]:
        """获取指定任务的相关记忆"""
        return [m for m in self.memories if m.task_id == task_id]
    
    def get_context(self, task_id: str, query: str = "") -> str:
        """获取任务的上下文记忆"""
        memories = self.get_by_task(task_id)
        if query:
            memories = self.search(query, limit=5)
        
        if not memories:
            return ""
        
        lines = []
        for m in memories[:5]:
            lines.append(f"[{m.type}] {m.content}")
        return "\n".join(lines)
    
    def clear_old(self, days: int = 30):
        """清除过期记忆"""
        cutoff = time.time() - (days * 86400)
        self.memories = [m for m in self.memories 
                        if datetime.fromisoformat(m.created_at).timestamp() > cutoff]
        self._save()
    
    def stats(self) -> Dict:
        """获取记忆统计"""
        return {
            "total": len(self.memories),
            "by_type": {
                t: len([m for m in self.memories if m.type == t])
                for t in ["preference", "fact", "decision", "context"]
            },
            "by_task": len(set(m.task_id for m in self.memories if m.task_id)),
        }


# ──────────────────────────────────────────────
# ContextWindow
# ──────────────────────────────────────────────

class ContextWindow:
    """上下文窗口管理器"""
    
    def __init__(self, max_tokens: int = 8000, model: str = "default"):
        self.max_tokens = max_tokens
        self.model = model
        self.estimator = TokenEstimator()
        self.summarizer = SummaryGenerator()
    
    def fit_messages(self, messages: List[Dict]) -> List[Dict]:
        """
        将消息适配到上下文窗口内
        
        策略：
        1. 计算总 token
        2. 如果超出，对早期消息进行摘要
        3. 保留最近的消息（更相关）
        """
        total = self.estimator.count_messages(messages, self.model)
        
        if total <= self.max_tokens:
            return messages  # 不需要压缩
        
        # 需要压缩
        return self._compress(messages, total)
    
    def _compress(self, messages: List[Dict], total_tokens: int) -> List[Dict]:
        """压缩消息列表"""
        # 保留最近的消息和摘要
        keep_recent = 6  # 保留最近 6 条
        recent = messages[-keep_recent:] if len(messages) > keep_recent else messages[:]
        
        # 对早期消息生成摘要
        old_messages = messages[:-keep_recent] if len(messages) > keep_recent else []
        summary = ""
        
        if old_messages:
            summary = self.summarizer.summarize(old_messages, max_tokens=self.max_tokens // 4)
        
        # 构建新的消息列表
        result = []
        
        # 添加系统消息
        system_msgs = [m for m in messages if m.get("role") == "system"]
        result.extend(system_msgs)
        
        # 添加摘要
        if summary:
            result.append({
                "role": "system",
                "content": f"[对话摘要]\n{summary}",
                "_summary": True,
            })
        
        # 添加最近消息
        result.extend(recent)
        
        return result
    
    def get_budget(self, messages: List[Dict]) -> int:
        """计算剩余 token 预算"""
        used = self.estimator.count_messages(messages, self.model)
        return max(0, self.max_tokens - used)
    
    def should_compress(self, messages: List[Dict]) -> bool:
        """判断是否需要压缩"""
        return self.estimator.count_messages(messages, self.model) > self.max_tokens * 0.8


# ──────────────────────────────────────────────
# 用法示例
# ──────────────────────────────────────────────

if __name__ == "__main__":
    # 测试 Token 估算
    print("=== Token Estimator ===")
    text = "这是一个测试文本，用于估算 token 数量。"
    print(f"文本: {text}")
    print(f"估算 token: {TokenEstimator.estimate(text)}")
    
    # 测试记忆系统
    print("\n=== Memory System ===")
    memory = MemorySystem("/tmp/test-memory.json")
    memory.add("preference", "用户偏好使用 Go 语言", tags=["lang", "go"], task_id="task1")
    memory.add("decision", "采用微服务架构", tags=["arch"], task_id="task1")
    memory.add("fact", "creative-platform 有 5 个模块", tags=["project"], task_id="task2")
    
    print(f"记忆统计: {memory.stats()}")
    print(f"搜索 'Go': {len(memory.search('Go'))} 条")
    
    # 测试上下文压缩
    print("\n=== Context Window ===")
    cw = ContextWindow(max_tokens=1000)
    messages = [
        {"role": "user", "content": f"消息{i}: 这是测试内容" * 50}
        for i in range(20)
    ]
    print(f"原始消息数: {len(messages)}")
    print(f"压缩后: {len(cw.fit_messages(messages))}")
    print(f"预算剩余: {cw.get_budget(messages)} tokens")
