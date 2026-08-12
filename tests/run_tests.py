#!/usr/bin/env python3
"""Manual test runner for biz-delivery tests (no pytest dependency)."""

import sys
import time
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


def test_intent_extraction():
    """Test intent extraction."""
    from scripts.query import extract_intent
    
    assert extract_intent("").isdigit() == False
    assert extract_intent("查看素材流程")[0] == "query"
    assert extract_intent("为什么竞价失败")[0] == "question"
    print("  ✓ Intent extraction")


def test_fuzzy_score():
    """Test fuzzy score calculation."""
    from scripts.query import fuzzy_score
    
    assert fuzzy_score("素材", "素材") == 1.0
    assert fuzzy_score("creative", "creative") == 1.0
    assert fuzzy_score("test", "") == 0.0
    print("  ✓ Fuzzy score")


def test_synonym_expansion():
    """Test synonym expansion."""
    from scripts.query import expand_synonyms
    
    keywords = expand_synonyms("素材")
    assert "素材" in keywords
    assert "creative" in keywords
    
    keywords = expand_synonyms("竞价")
    assert "竞价" in keywords
    assert "bidding" in keywords
    print("  ✓ Synonym expansion")


def test_search_code():
    """Test code search."""
    from scripts.query import search_code
    
    ir_data = {
        "functions": [
            {"name": "PlaceBid", "signature": "ctx, req", "file": "bid.go"}
        ],
        "routes": [
            {"method": "POST", "path": "/api/bid", "handler": "PlaceBid"}
        ]
    }
    results = search_code(ir_data, ["PlaceBid"])
    assert len(results) > 0
    assert any(r["type"] == "function" for r in results)
    print("  ✓ Code search")


def test_rrf_fusion():
    """Test RRF fusion."""
    from scripts.query import rrf_fuse
    
    candidates = [
        [{"name": "A", "score": 0.9}, {"name": "B", "score": 0.8}],
        [{"name": "B", "score": 0.85}, {"name": "C", "score": 0.7}]
    ]
    result = rrf_fuse(candidates)
    assert len(result) > 0
    print("  ✓ RRF fusion")


def test_performance():
    """Test performance."""
    from scripts.query import extract_intent, fuzzy_score
    
    start = time.time()
    for _ in range(1000):
        extract_intent("查看素材审核流程")
        fuzzy_score("素材", "creative")
    elapsed = time.time() - start
    
    assert elapsed < 1.0, f"Performance test failed: {elapsed}s"
    print(f"  ✓ Performance ({elapsed:.3f}s for 2000 ops)")


def main():
    print("=" * 50)
    print("biz-delivery Query Module Tests")
    print("=" * 50)
    print()
    
    tests = [
        ("Intent Extraction", test_intent_extraction),
        ("Fuzzy Score", test_fuzzy_score),
        ("Synonym Expansion", test_synonym_expansion),
        ("Code Search", test_search_code),
        ("RRF Fusion", test_rrf_fusion),
        ("Performance", test_performance),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            failed += 1
    
    print()
    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
