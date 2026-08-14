#!/usr/bin/env python3
"""对话式技术方案生成器 — LLM 可主动追问细节

支持两阶段模式：
1. 首次生成：基于 PRD + IR 生成初始 TD
2. 追问模式：LLM 提出澄清问题，用户回答后再生成最终 TD

Usage:
    # 阶段1: 生成初始 TD + 问题列表
    python3 scripts/conversation_td.py --mode draft --profile profiles/default.json --text "..."

    # 阶段2: 提供答案，生成最终 TD
    python3 scripts/conversation_td.py --mode answer \
        --profile profiles/default.json --text "..." \
        --answers '{"q1": "answer1", "q2": "answer2"}'
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional


# 默认必须澄清的问题模板（覆盖常见架构决策盲区）
DEFAULT_CLARIFICATION_QUESTIONS = [
    {
        "id": "q1",
        "question": "这个功能是否涉及现有数据的变更？需要数据迁移吗？",
        "category": "data_migration",
        "priority": "high",
    },
    {
        "id": "q2",
        "question": "是否需要兼容旧版本 API？是否有 breaking change？",
        "category": "compatibility",
        "priority": "high",
    },
    {
        "id": "q3",
        "question": "并发量级预期？QPS 峰值大约是多少？",
        "category": "performance",
        "priority": "medium",
    },
    {
        "id": "q4",
        "question": "是否需要灰度发布或 Feature Flag 控制？",
        "category": "deployment",
        "priority": "medium",
    },
    {
        "id": "q5",
        "question": "是否有已有的中间件/SDK 可以使用？",
        "category": "existing_code",
        "priority": "low",
    },
]


class ConversationTDEngine:
    """对话式技术方案生成引擎。"""

    def __init__(self, profile: dict, output_dir: str, wiki_path: Optional[str] = None,
                 module_filter: Optional[str] = None, max_files: Optional[int] = None):
        from base_engine import EngineBase
        self.engine = EngineBase(profile, output_dir, wiki_path,
                                 module_filter=module_filter, max_files=max_files)
        self.profile = self.engine._normalize_profile(profile)
        self.output_dir = Path(output_dir)
        self.qa_history: List[Dict] = []  # 问题-答案历史记录

    def generate_draft(self, prd_text: str) -> Dict:
        """生成初始 TD + 澄清问题列表。

        Returns:
            {
                "status": "needs_clarification" | "ready",
                "draft_td": str,          # 初始技术方案（不完整）
                "questions": [...],       # 需要澄清的问题
                "clarification_count": int,
            }
        """
        print("\n📋 Stage 1: Generating initial TD draft...")

        # Scan codebase
        ir = self.engine._scan_codebase()
        cache_dir = str(self.output_dir)
        filtered = self.engine._query_evidence_for_prd(prd_text, cache_dir)

        # Build draft prompt (same as TDEngine but with clarification section)
        from td_engine import TDEngine
        td_engine = TDEngine(self.profile, cache_dir, wiki_path=None,
                             module_filter=self.engine.module_filter,
                             max_files=self.engine.max_files)
        prompt = td_engine._build_td_prompt(filtered, ir, prd_text, review_report=None)

        # Append clarification questions
        prompt += "\n\n## 📌 澄清问题（请逐条回答以完善方案）\n\n"
        for q in DEFAULT_CLARIFICATION_QUESTIONS:
            prompt += f"**[{q['priority']}] {q['id']}**: {q['question']}\n\n"

        # Save draft
        draft_file = self.output_dir / "td_draft.md"
        draft_file.write_text(prompt, encoding="utf-8")

        result = {
            "status": "needs_clarification",
            "draft_file": str(draft_file),
            "draft_td": prompt,
            "questions": DEFAULT_CLARIFICATION_QUESTIONS,
            "clarification_count": len(DEFAULT_CLARIFICATION_QUESTIONS),
            "prompt_tokens": _estimate_tokens(prompt),
        }

        print(f"  ✅ Draft saved to {draft_file}")
        print(f"  📊 Prompt: {result['prompt_tokens']} tokens")
        print(f"  ❓ {result['clarification_count']} clarification questions generated")

        return result

    def generate_final(self, prd_text: str, answers: Dict[str, str]) -> Dict:
        """基于答案生成最终技术方案。

        Args:
            prd_text: PRD 内容
            answers: {question_id: answer} 映射

        Returns:
            {
                "status": "completed",
                "final_td_file": str,
                "qa_history": [...],
            }
        """
        print("\n📋 Stage 2: Generating final TD with answers...")

        # Record Q&A
        for q in DEFAULT_CLARIFICATION_QUESTIONS:
            ans = answers.get(q["id"], "")
            self.qa_history.append({
                "question": q["question"],
                "answer": ans,
                "category": q["category"],
            })

        # Scan codebase
        ir = self.engine._scan_codebase()
        cache_dir = str(self.output_dir)
        filtered = self.engine._query_evidence_for_prd(prd_text, cache_dir)

        # Build enhanced TD prompt with answers
        from td_engine import TDEngine
        td_engine = TDEngine(self.profile, cache_dir, wiki_path=None,
                             module_filter=self.engine.module_filter,
                             max_files=self.engine.max_files)
        prompt = td_engine._build_td_prompt(filtered, ir, prd_text, review_report=None)

        # Inject Q&A context
        qa_section = "\n\n## ✅ 已澄清问题（基于问答补充的上下文）\n\n"
        for entry in self.qa_history:
            qa_section += f"- **{entry['category']}**: {entry['question']}\n"
            qa_section += f"  答: {entry['answer']}\n\n"
        prompt += qa_section

        # Save final TD
        final_file = self.output_dir / "technical_design.md"
        final_file.write_text(prompt, encoding="utf-8")

        # Save Q&A history
        qa_file = self.output_dir / "td_qa_history.json"
        qa_file.write_text(json.dumps(self.qa_history, ensure_ascii=False, indent=2))

        result = {
            "status": "completed",
            "final_td_file": str(final_file),
            "qa_history": self.qa_history,
            "prompt_tokens": _estimate_tokens(prompt),
        }

        print(f"  ✅ Final TD saved to {final_file}")
        print(f"  📊 Prompt: {result['prompt_tokens']} tokens")
        print(f"  💬 Q&A history: {len(self.qa_history)} exchanges")

        return result


def _estimate_tokens(text: str) -> int:
    """Rough token estimation."""
    if not text:
        return 0
    import re
    cn_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    other_chars = len(text) - cn_chars
    return int(cn_chars + other_chars / 3.5)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Conversation-based TD generation")
    parser.add_argument("--mode", required=True, choices=["draft", "answer"])
    parser.add_argument("--profile", required=True)
    parser.add_argument("--text", required=True, help="PRD content")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--answers", help="JSON string of answers: '{\"q1\": \"answer1\"}'")
    args = parser.parse_args()

    with open(args.profile) as f:
        profile = json.load(f)

    engine = ConversationTDEngine(profile, args.output_dir)

    if args.mode == "draft":
        result = engine.generate_draft(args.text)
        print(f"\nStatus: {result['status']}")
        print(f"Draft file: {result['draft_file']}")
        print(f"Questions: {result['clarification_count']}")
    elif args.mode == "answer":
        answers = json.loads(args.answers) if args.answers else {}
        result = engine.generate_final(args.text, answers)
        print(f"\nStatus: {result['status']}")
        print(f"Final TD: {result['final_td_file']}")
