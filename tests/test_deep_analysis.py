"""Deep analysis pipeline tests."""
import pytest
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestDeepAnalysis:
    """测试深度分析管线."""
    
    DAP_PATH = "/Users/yanping.ma/GolandProjects/dap"
    
    def test_detect_language(self):
        from scripts.project_auto_detector import detect_project
        det = detect_project(self.DAP_PATH)
        assert det["language"] == "go"
        assert det["architecture"] == "microservice"
        assert det["scale"] == "large"
    
    def test_generate_profile(self):
        from scripts.project_auto_detector import detect_project, generate_profile
        det = detect_project(self.DAP_PATH)
        profile = generate_profile(det)
        assert "business_domain" in profile
        assert len(profile["repositories"]) == 1
        assert profile["repositories"][0]["language"] == "go"
    
    def test_scan_ir(self):
        from scripts.learn_repo import GoScanner
        scanner = GoScanner()
        ir = scanner.scan_directory(Path(self.DAP_PATH), max_files=500)
        assert ir.structs is not None
        assert ir.functions is not None
        assert len(ir.structs) > 0 or len(ir.functions) > 0
    
    def test_patterns_detection(self):
        from scripts.go_flow_analyzer import analyze_patterns
        results = analyze_patterns([self.DAP_PATH])
        assert "state_machines" in results
        assert "redis_locks" in results
        assert "kafka_patterns" in results
        assert "enums" in results
        assert isinstance(results["enums"], list)
    
    def test_mermaid_generation(self):
        from scripts.mermaid_generator import MermaidGenerator
        gen = MermaidGenerator({}, flow_data={})
        diagram = gen.generate_facebook_sync_flow_diagram()
        assert "```mermaid" in diagram
        assert "flowchart TB" in diagram
    
    def test_mermaid_sequence(self):
        from scripts.mermaid_generator import MermaidGenerator
        gen = MermaidGenerator({}, flow_data={})
        diagram = gen.generate_ads_change_sync_diagram()
        assert "```mermaid" in diagram
        assert "sequenceDiagram" in diagram
