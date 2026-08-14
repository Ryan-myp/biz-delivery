"""Project auto detector tests."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.project_auto_detector import (
    detect_language, detect_framework, detect_architecture,
    estimate_scale, find_entry_points, detect_project, generate_profile,
)


class TestProjectAutoDetector:
    """测试项目自动检测器."""
    
    DAP_PATH = "/Users/yanping.ma/GolandProjects/dap"
    ADP_PATH = "/Users/yanping.ma/GolandProjects/ad_delivery_platform"
    
    def test_detect_language_go(self):
        lang = detect_language(Path(self.DAP_PATH))
        assert lang == "go"
    
    def test_detect_language_adp(self):
        lang = detect_language(Path(self.ADP_PATH))
        assert lang == "go"
    
    def test_detect_framework_spex(self):
        fw = detect_framework(Path(self.ADP_PATH), "go")
        assert fw == "spex"
    
    def test_detect_framework_gin(self):
        fw = detect_framework(Path(self.DAP_PATH), "go")
        # dap uses spex but also gin
        assert fw in ("gin", "spex")
    
    def test_detect_architecture_microservice(self):
        arch = detect_architecture(Path(self.DAP_PATH), "go")
        assert arch == "microservice"
    
    def test_detect_scale_large(self):
        info = estimate_scale(Path(self.DAP_PATH), "go")
        assert info["scale"] == "large"
        assert info["max_files"] >= 2000
    
    def test_detect_scale_medium(self):
        info = estimate_scale(Path(self.ADP_PATH), "go")
        assert info["scale"] == "large"
    
    def test_find_entry_points(self):
        entries = find_entry_points(Path(self.DAP_PATH), "go")
        assert len(entries) > 0
        assert any("main.go" in e for e in entries)
    
    def test_detect_project(self):
        result = detect_project(self.DAP_PATH)
        assert result["language"] == "go"
        assert result["architecture"] == "microservice"
        assert result["scale"] == "large"
        assert result["max_files"] > 0
    
    def test_generate_profile(self):
        det = detect_project(self.DAP_PATH)
        profile = generate_profile(det)
        assert "business_domain" in profile
        assert "repositories" in profile
        assert len(profile["repositories"]) == 1
        assert profile["repositories"][0]["language"] == "go"
    
    def test_detect_project_not_found(self):
        result = detect_project("/nonexistent/path")
        assert "error" in result
