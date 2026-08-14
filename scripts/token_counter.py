#!/usr/bin/env python3
"""Token counter and prompt chunker for large project support.

Provides:
1. Rough token estimation (Chinese + English mixed text)
2. Smart prompt chunking with overlap
3. Context budget management per engine stage
"""

import re
from typing import List, Tuple


# Estimated tokens per character (mix of Chinese and English)
# Chinese: ~1 char = 1-2 tokens, English: ~4 chars = 1 token
TOKEN_CHARS_RATIO = 3.5  # Conservative average


def estimate_tokens(text: str) -> int:
    """Estimate token count for mixed Chinese/English text."""
    if not text:
        return 0
    # Count Chinese characters separately
    cn_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    # Count non-Chinese characters
    other_chars = len(text) - cn_chars
    # Chinese: ~1 token per char, English/code: ~1 token per 4 chars
    return int(cn_chars + other_chars / TOKEN_CHARS_RATIO)


def truncate_to_budget(text: str, max_tokens: int, min_tokens: int = 100) -> Tuple[str, int]:
    """Truncate text to fit within token budget, preserving structure.
    
    Returns:
        (truncated_text, actual_token_count)
    """
    current_tokens = estimate_tokens(text)
    if current_tokens <= max_tokens:
        return text, current_tokens
    
    # Simple character-level truncation with ellipsis
    ratio = max_tokens / current_tokens
    trunc_len = int(len(text) * ratio)
    trunc_len = max(trunc_len, min_tokens * TOKEN_CHARS_RATIO)
    return text[:trunc_len] + "\n\n... [内容被截断，原始文本超出token限制]", current_tokens


def chunk_prompt(prompt: str, chunk_size_tokens: int = 8000, overlap_tokens: int = 500) -> List[str]:
    """Split a large prompt into chunks with overlap for sequential LLM calls.
    
    Strategy:
    - Split by logical sections (## headers)
    - Each chunk stays within chunk_size_tokens
    - Overlap preserves context between chunks
    """
    if estimate_tokens(prompt) <= chunk_size_tokens:
        return [prompt]
    
    # Split by section headers
    sections = re.split(r'(?=^## )', prompt, flags=re.MULTILINE)
    sections = [s.strip() for s in sections if s.strip()]
    
    chunks = []
    current_chunk = []
    current_tokens = 0
    
    for section in sections:
        section_tokens = estimate_tokens(section)
        
        # If single section exceeds chunk size, split it further
        if section_tokens > chunk_size_tokens:
            # Flush current chunk first
            if current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
                current_tokens = 0
            
            # Split oversized section by paragraphs
            paragraphs = section.split('\n\n')
            para_chunk = []
            para_tokens = 0
            for para in paragraphs:
                para_tok = estimate_tokens(para)
                if para_tok > chunk_size_tokens:
                    # Split by lines
                    lines = para.split('\n')
                    line_chunk = []
                    line_tokens = 0
                    for line in lines:
                        line_tok = estimate_tokens(line)
                        if line_tokens + line_tok > chunk_size_tokens and line_chunk:
                            chunks.append('\n'.join(line_chunk))
                            line_chunk = [line]
                            line_tokens = line_tok
                        else:
                            line_chunk.append(line)
                            line_tokens += line_tok
                    if line_chunk:
                        chunks.append('\n'.join(line_chunk))
                else:
                    if para_tokens + para_tok > chunk_size_tokens:
                        chunks.append('\n\n'.join(para_chunk))
                        # Keep overlap: last paragraph as overlap
                        overlap_start = max(0, len(para_chunk) - 2)
                        para_chunk = para_chunk[overlap_start:]
                        para_tokens = estimate_tokens('\n\n'.join(para_chunk))
                    para_chunk.append(para)
                    para_tokens += para_tok
            if para_chunk:
                chunks.append('\n\n'.join(para_chunk))
            continue
        
        if current_tokens + section_tokens > chunk_size_tokens and current_chunk:
            # Flush current chunk
            chunks.append("\n".join(current_chunk))
            # Overlap: keep last 1-2 sections
            overlap_n = 2
            overlap_sections = current_chunk[-overlap_n:] if len(current_chunk) >= overlap_n else current_chunk[:]
            current_chunk = overlap_sections
            current_tokens = estimate_tokens("\n".join(current_chunk))
        
        current_chunk.append(section)
        current_tokens += section_tokens
    
    if current_chunk:
        chunks.append("\n".join(current_chunk))
    
    return chunks if chunks else [prompt]


def format_context_budget(context_name: str, used_tokens: int, budget_tokens: int) -> str:
    """Format context budget info for logging."""
    pct = (used_tokens / budget_tokens * 100) if budget_tokens > 0 else 0
    status = "✅" if pct <= 80 else ("⚠️" if pct <= 100 else "❌")
    return f"{status} {context_name}: {used_tokens}/{budget_tokens} tokens ({pct:.0f}%)"
