#!/usr/bin/env python3
"""Unified LLM client for biz-delivery engines.

Provides a single entry point for all LLM API calls across review, TD, and test engines.
Supports both synchronous and streaming modes, with retry logic and token counting.

Usage:
    from llm_client import LLMClient
    
    # Initialize with API key
    client = LLMClient(api_key="your-key", model="agnes-2.0-flash")
    
    # Simple chat
    result = client.chat("What is 2+2?")
    print(result.content)
    
    # Structured output (JSON)
    result = client.chat_structured(
        "Analyze this PRD...", 
        schema={"issues": [{"title": str, "severity": str}]}
    )
"""

import json
import time
import hashlib
from typing import Any, Dict, List, Optional
from pathlib import Path


# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

_DEFAULT_API_URL = "https://apihub.agnes-ai.com/v1/chat/completions"
_DEFAULT_MODEL = "agnes-2.0-flash"
_DEFAULT_MAX_TOKENS = 8192
_DEFAULT_TEMPERATURE = 0.1
_DEFAULT_TIMEOUT = 120
_DEFAULT_RETRIES = 3
_RETRY_DELAY = 2  # seconds


class LLMClient:
    """Unified LLM client for biz-delivery engines."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: str = _DEFAULT_API_URL,
        model: str = _DEFAULT_MODEL,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
        temperature: float = _DEFAULT_TEMPERATURE,
        timeout: int = _DEFAULT_TIMEOUT,
        retries: int = _DEFAULT_RETRIES,
    ):
        self.api_url = api_url
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout
        self.retries = retries
        self.retry_delay = _RETRY_DELAY
        
        # Load API key from environment or config file
        if not api_key:
            api_key = self._load_api_key()
        
        if not api_key:
            raise ValueError(
                "API key not found. Set AGNES_API_KEY env var or pass api_key parameter."
            )
        
        self.api_key = api_key
        self._call_count = 0
        self._total_tokens = 0
    
    def _load_api_key(self) -> str:
        """Load API key from environment variable or config file."""
        import os
        key = os.environ.get("AGNES_API_KEY")
        if key:
            return key
        
        # Try config file
        config_paths = [
            Path.home() / ".hermes" / "config.yaml",
            Path(__file__).parent / ".." / "profiles" / "default.json",
        ]
        for cfg_path in config_paths:
            try:
                if cfg_path.suffix == ".yaml":
                    import yaml
                    with open(cfg_path) as f:
                        cfg = yaml.safe_load(f)
                    key = cfg.get("llm", {}).get("api_key", "")
                    if key:
                        return key
                elif cfg_path.suffix == ".json":
                    with open(cfg_path) as f:
                        cfg = json.load(f)
                    key = cfg.get("api_key", cfg.get("profile", {}).get("api_key", ""))
                    if key:
                        return key
            except Exception:
                continue
        return ""
    
    def _build_request(self, messages: List[Dict], **kwargs) -> Dict[str, Any]:
        """Build the API request payload."""
        body = {
            "model": kwargs.get("model", self.model),
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
        }
        
        # Support structured output
        if kwargs.get("response_format"):
            body["response_format"] = {"type": "json_schema", "json_schema": kwargs["response_format"]}
        
        # Support tools/function calling
        if kwargs.get("tools"):
            body["tools"] = kwargs["tools"]
        
        return body
    
    def _make_call(self, body: Dict, messages: List[Dict]) -> Dict[str, Any]:
        """Make the actual API call with retry logic."""
        import urllib.request
        import urllib.error
        
        url = self.api_url
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        
        payload = json.dumps(body).encode("utf-8")
        
        last_error = None
        for attempt in range(self.retries):
            try:
                req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read().decode("utf-8")
                    result = json.loads(raw)
                    
                    # Track usage
                    usage = result.get("usage", {})
                    self._call_count += 1
                    self._total_tokens += usage.get("total_tokens", 0)
                    
                    return result
                    
            except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, Exception) as e:
                last_error = e
                if attempt < self.retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
        
        raise RuntimeError(f"LLM API call failed after {self.retries} attempts: {last_error}")
    
    def chat(self, prompt: str, system: str = "", **kwargs) -> Dict[str, Any]:
        """Send a chat message and return the full response.
        
        Args:
            prompt: User message content
            system: System prompt (optional)
            **kwargs: Additional params (model, max_tokens, temperature)
            
        Returns:
            Full API response dict with 'content' field
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        body = self._build_request(messages, **kwargs)
        result = self._make_call(body, messages)
        
        choices = result.get("choices", [])
        if not choices:
            return {"content": "", "raw": result}
        
        choice = choices[0]
        content = choice.get("message", {}).get("content", "")
        
        return {
            "content": content,
            "raw": result,
            "finish_reason": choice.get("finish_reason"),
            "usage": result.get("usage", {}),
        }
    
    def chat_with_messages(self, messages: List[Dict], **kwargs) -> Dict[str, Any]:
        """Send multiple messages and return the response.
        
        Args:
            messages: List of {role, content} dicts
            **kwargs: Additional params
            
        Returns:
            Response dict with 'content' field
        """
        body = self._build_request(messages, **kwargs)
        result = self._make_call(body, messages)
        
        choices = result.get("choices", [])
        if not choices:
            return {"content": "", "raw": result}
        
        return {
            "content": choices[0].get("message", {}).get("content", ""),
            "raw": result,
            "finish_reason": choices[0].get("finish_reason"),
            "usage": result.get("usage", {}),
        }
    
    def chat_json(self, prompt: str, system: str = "", **kwargs) -> Dict[str, Any]:
        """Send a chat message expecting JSON response.
        
        Automatically adds JSON formatting instructions to the system prompt.
        
        Returns:
            Parsed JSON dict, or {'_error': str} on failure
        """
        default_system = (
            "You are a precise assistant that returns valid JSON. "
            "Only output JSON, no markdown fences, no explanations."
        )
        system = system or default_system
        
        response = self.chat(prompt, system=system, **kwargs)
        content = response.get("content", "").strip()
        
        # Try parsing as JSON directly
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        # Try extracting JSON from markdown code blocks
        import re
        json_match = re.search(r'```(?:json)?\s*(.*?)\n```', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except json.JSONDecodeError:
                pass
        
        # Return raw with error marker
        return {"_error": f"Failed to parse JSON from LLM response", "_raw": content}
    
    def hash_prompt(self, prompt: str) -> str:
        """Generate a cache key for a prompt."""
        return hashlib.sha256(prompt.encode()).hexdigest()[:16]
    
    def get_stats(self) -> Dict[str, int]:
        """Return usage statistics."""
        return {
            "total_calls": self._call_count,
            "total_tokens": self._total_tokens,
        }


# ──────────────────────────────────────────────
# Prompt templating helpers
# ──────────────────────────────────────────────

def build_review_prompt(prd_text: str, ir_summary: str, evidence: list, prechecks: list) -> str:
    """Build a structured PRD review prompt with evidence citations.
    
    This replaces the old _build_review_prompt in review_engine.py.
    Key improvements:
    1. Evidence items include source references (file:line)
    2. Pre-check results are injected as structured data
    3. Output format is strictly defined for parsing
    """
    prompt_parts = []
    
    # Role definition
    prompt_parts.append("""You are a senior software architect reviewing a Product Requirements Document (PRD) against the existing codebase.

Your job is to find issues that would cause problems during implementation. Focus on:
1. **Correctness**: Does the PRD conflict with existing architecture?
2. **Completeness**: Are there missing scenarios, edge cases, or error handling?
3. **Feasibility**: Can this be implemented with the current tech stack?
4. **Risk**: What are the performance, security, and compatibility risks?

Output your review in the EXACT format specified below. Do NOT add extra commentary.""")
    prompt_parts.append("")
    
    # Codebase context
    prompt_parts.append("--- CODEBASE CONTEXT ---")
    prompt_parts.append(ir_summary)
    prompt_parts.append("")
    
    # Pre-check results (static analysis findings before LLM review)
    if prechecks:
        prompt_parts.append("--- PRE-CHECK RESULTS (Static Analysis) ---")
        for pc in prechecks:
            severity = pc.get('severity', 'info').upper()
            desc = pc.get('description', pc.get('message', ''))
            suggestion = pc.get('suggestion', '')
            prompt_parts.append(f"[{severity}] {desc}")
            if suggestion:
                prompt_parts.append(f"  → Suggestion: {suggestion}")
        prompt_parts.append("")
    
    # Evidence with citations
    if evidence:
        prompt_parts.append("--- EVIDENCE FROM CODEBASE ---")
        for i, item in enumerate(evidence[:20], 1):
            title = item.get('title', item.get('path', 'unknown'))
            score = item.get('score', 0)
            content = item.get('content', item.get('text', ''))
            source = item.get('source', item.get('path', ''))
            item_type = item.get('type', 'unknown')
            
            prompt_parts.append(f"Evidence #{i} (type={item_type}, score={score:.3f}, source={source}):")
            prompt_parts.append(f"Title: {title}")
            if content:
                prompt_parts.append(f"Content: {content[:300]}")
            prompt_parts.append("")
    
    # PRD content
    prompt_parts.append("--- PRD CONTENT ---")
    prompt_parts.append(prd_text)
    prompt_parts.append("")
    
    # Output format specification
    prompt_parts.append("""--- OUTPUT FORMAT ---
Return your review as a Markdown document with these EXACT sections:

## 1. Overall Assessment
Status: [Pass | Needs Revision | Blocked]
Confidence: [High | Medium | Low]
Summary: 1-2 sentence summary

## 2. Critical Issues (P0)
Issues that MUST be resolved before implementation. Each issue should cite evidence:
- [P0] Issue title — Brief description. Evidence: #N (refers to Evidence # above)

## 3. Important Issues (P1)
Issues that should be resolved but may not block implementation:
- [P1] Issue title — Brief description. Evidence: #N

## 4. Minor Issues (P2)
Suggestions for improvement:
- [P2] Issue title — Brief description

## 5. Section-by-Section Review
### 5.1 Correctness Check
Analysis of whether PRD conflicts with existing architecture...

### 5.2 Scenario Completeness
Missing user flows, edge cases, error paths...

### 5.3 Compatibility Analysis
Impact on existing APIs, data models, backward compatibility...

### 5.4 Risk Assessment
Performance, security, operational risks...

## 6. Recommendations
Actionable next steps for the product team and engineering team.

---
IMPORTANT RULES:
1. Every P0/P1 issue MUST reference at least one Evidence # from the codebase
2. Do NOT invent features or requirements not mentioned in the PRD
3. If the PRD is well-aligned with the codebase, state so explicitly
4. Keep each issue description under 100 characters for scannability""")
    
    return "\n".join(prompt_parts)


def build_td_prompt(prd_text: str, review_report: str, ir_summary: str, 
                    diagrams: str, evidence: list) -> str:
    """Build a structured Technical Design prompt with evidence citations.
    
    Key improvements:
    1. Incorporates review findings into design decisions
    2. Requires concrete code-level details (struct fields, function signatures)
    3. Mandates mermaid diagrams for architecture and data flow
    """
    prompt_parts = []
    
    prompt_parts.append("""You are a senior software architect designing a technical solution for the following PRD.

CRITICAL: You must base your design on the ACTUAL codebase structure provided. Do NOT invent modules, packages, or patterns that don't exist.

Output your design in the EXACT format specified below.""")
    prompt_parts.append("")
    
    prompt_parts.append("--- CODEBASE CONTEXT ---")
    prompt_parts.append(ir_summary)
    prompt_parts.append("")
    
    if diagrams:
        prompt_parts.append("--- AUTO-GENERATED DIAGRAMS ---")
        prompt_parts.append(diagrams)
        prompt_parts.append("")
    
    if review_report:
        prompt_parts.append("--- PRD REVIEW FINDINGS ---")
        prompt_parts.append(review_report)
        prompt_parts.append("")
    
    if evidence:
        prompt_parts.append("--- RELEVANT CODE EVIDENCE ---")
        for i, item in enumerate(evidence[:15], 1):
            title = item.get('title', item.get('path', 'unknown'))
            content = item.get('content', item.get('text', ''))
            prompt_parts.append(f"#{i}: {title}")
            if content:
                prompt_parts.append(f"   {content[:200]}")
        prompt_parts.append("")
    
    prompt_parts.append("--- PRD ---")
    prompt_parts.append(prd_text)
    prompt_parts.append("")
    
    prompt_parts.append("""--- OUTPUT FORMAT ---
## 1. Design Decision
Type: [Enhancement | New Feature | Hybrid]
Rationale: Why this approach...

## 2. Architecture Design
### 2.1 Module Structure
List the exact Go packages/modules that will be created/modified:
- `pkg/service/adgroup/` — (existing) handles ad group CRUD
- `pkg/service/adgroup/bidding.go` — (new) bidding logic integration

### 2.2 Component Diagram
Provide a mermaid graph showing component relationships:
```mermaid
graph LR
    Handler[Handler Layer] --> Service[Service Layer]
    Service --> DAO[DAO Layer]
    Service --> Cache[Redis Cache]
```

## 3. Data Model Changes
### 3.1 Database Schema
For each table change, provide:
- Table name
- Columns (with types, nullable, defaults)
- Indexes
- Migration direction (add/drop/alter)

### 3.2 Go Struct Definitions
Provide the EXACT struct definitions:
```go
type AdGroupBiddingConfig struct {
    ID          uint      `json:"id" gorm:"primaryKey"`
    AdGroupID   uint      `json:"ad_group_id"`
    Strategy    string    `json:"strategy"`
    MaxBidPrice decimal.Decimal `json:"max_bid_price"`
    CreatedAt   time.Time `json:"created_at"`
}
```

## 4. API Design
For each new/modified endpoint:
- HTTP Method + Path
- Request struct (exact Go type)
- Response struct (exact Go type)
- Error codes returned
- Auth requirements

Example:
```
POST /api/v1/adgroups/{id}/bidding
Request:  BiddingConfig{Strategy: "max_cpc", MaxBidPrice: 5.00}
Response: BiddingConfigResponse{ID: 123, Status: "active"}
Errors:   ERR_BIDDING_INVALID_STRATEGY, ERR_BIDDING_PRICE_EXCEEDED
Auth:     Admin role required
```

## 5. Implementation Plan
### 5.1 File-by-file changes
| File | Action | Description |
|------|--------|-------------|
| pkg/service/adgroup/bidding.go | NEW | Bidding strategy service |
| pkg/handler/adgroup.go | MODIFY | Add bidding handler |
| internal/db/migration/xxx.sql | NEW | Schema migration |

### 5.2 Dependencies
- New: github.com/shopspring/decimal (for precise pricing)
- Existing: pkg/dao/adgroup/ (reuse for CRUD)

## 6. Risk & Mitigation
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Bidding API latency | High | Medium | Add Redis cache for hot configs |

## 7. Testing Strategy
- Unit tests: Mock DAO layer, test bidding strategy logic
- Integration tests: End-to-end bidding flow with real DB
- Performance tests: Simulate 1000 QPS bidding requests""")
    
    return "\n".join(prompt_parts)


def build_test_prompt(prd_text: str, td_text: str, ir_summary: str, 
                      routes: list, functions: list, error_codes: list) -> str:
    """Build a structured test case generation prompt.
    
    Key improvements:
    1. Uses actual route/function signatures from IR
    2. References real error codes for assertion
    3. Requires boundary values derived from field types
    """
    prompt_parts = []
    
    prompt_parts.append("""You are a senior QA engineer generating comprehensive test cases.

CRITICAL: Base your test cases on the ACTUAL codebase structure. Use real route paths, function signatures, and error codes from the evidence below.

Output your test cases as a Markdown table.""")
    prompt_parts.append("")
    
    prompt_parts.append("--- CODEBASE CONTEXT ---")
    prompt_parts.append(ir_summary)
    prompt_parts.append("")
    
    if routes:
        prompt_parts.append("--- ACTUAL ROUTES ---")
        for r in routes[:20]:
            method = r.get('method', '*')
            path = r.get('path', '')
            handler = r.get('handler', '')
            prompt_parts.append(f"  {method.upper()} {path} → {handler}")
        prompt_parts.append("")
    
    if functions:
        prompt_parts.append("--- KEY FUNCTIONS ---")
        for f in functions[:15]:
            name = f.get('name', f.get('func_name', ''))
            pkg = f.get('package', f.get('pkg', ''))
            params = f.get('params', '')
            ret = f.get('returns', f.get('return_types', ''))
            prompt_parts.append(f"  {pkg}.{name}({params}) ({ret})")
        prompt_parts.append("")
    
    if error_codes:
        prompt_parts.append("--- ERROR CODES ---")
        for ec in error_codes[:20]:
            code = ec.get('code', ec.get('name', ''))
            msg = ec.get('message', ec.get('desc', ''))
            prompt_parts.append(f"  {code}: {msg}")
        prompt_parts.append("")
    
    if td_text:
        prompt_parts.append("--- TECHNICAL DESIGN ---")
        prompt_parts.append(td_text[:3000])
        prompt_parts.append("")
    
    prompt_parts.append("--- PRD ---")
    prompt_parts.append(prd_text)
    prompt_parts.append("")
    
    prompt_parts.append("""--- OUTPUT FORMAT ---
Generate test cases in a Markdown table with these columns:

| TC# | Category | Priority | Title | Preconditions | Steps | Expected Result | Error Code |
|-----|----------|----------|-------|---------------|-------|-----------------|------------|
| TC001 | Positive | P0 | Create ad group with valid config | User is logged in with admin role | 1. POST /api/v1/adgroups\\n2. Body: {...} | 201 Created, returns ad_group_id | (none) |
| TC002 | Exception | P0 | Create ad group with invalid bid price | User is logged in with admin role | 1. POST /api/v1/adgroups\\n2. Body: {bid_price: -1} | 400 Bad Request | ERR_INVALID_BID_PRICE |

Categories: positive, exception, boundary, security, performance, compatibility
Priorities: P0 (core flow), P1 (important), P2 (nice to have)

Requirements:
1. Use ACTUAL route paths from the evidence section
2. Reference REAL error codes from the evidence section
3. Include at least 3 boundary test cases per feature
4. Include at least 2 security test cases (auth, injection, etc.)
5. For state machine operations, include transition validation tests""")
    
    return "\n".join(prompt_parts)


# ──────────────────────────────────────────────
# Convenience factory
# ──────────────────────────────────────────────

def create_client(profile: Optional[dict] = None, **kwargs) -> LLMClient:
    """Create an LLMClient from a profile dict or kwargs.
    
    Tries to extract api_key from profile first, then falls back to kwargs/env.
    """
    api_key = kwargs.pop("api_key", None)
    model = kwargs.pop("model", None)
    
    if profile:
        pdata = profile.get("profile", profile) if isinstance(profile, dict) else profile
        if not api_key:
            api_key = pdata.get("api_key", pdata.get("llm", {}).get("api_key"))
        if not model:
            model = pdata.get("model", pdata.get("llm", {}).get("model", _DEFAULT_MODEL))
    
    return LLMClient(
        api_key=api_key,
        model=model or _DEFAULT_MODEL,
        **kwargs,
    )
