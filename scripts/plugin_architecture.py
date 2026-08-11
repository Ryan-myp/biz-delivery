#!/usr/bin/env python3
"""
Plugin Architecture - 插件架构定义
支持扫描器、生成器、评估器插件化
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class PluginConfig:
    """插件配置"""
    name: str
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PluginResult:
    """插件结果"""
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


class BasePlugin(ABC):
    """插件基类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """插件名称"""
        pass
    
    @abstractmethod
    def initialize(self, config: PluginConfig) -> bool:
        """初始化插件"""
        pass
    
    @abstractmethod
    def execute(self, input_data: Dict[str, Any]) -> PluginResult:
        """执行插件逻辑"""
        pass
    
    @abstractmethod
    def destroy(self) -> None:
        """销毁插件"""
        pass
    
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """验证输入数据"""
        return isinstance(input_data, dict) and len(input_data) > 0


class ScannerPlugin(BasePlugin):
    """代码扫描器插件接口"""
    
    @abstractmethod
    def scan(self, repo_path: str, options: Dict[str, Any] = None) -> PluginResult:
        """扫描代码仓库"""
        pass


class GeneratorPlugin(BasePlugin):
    """知识生成器插件接口"""
    
    @abstractmethod
    def generate(self, ir_data: Dict[str, Any], options: Dict[str, Any] = None) -> PluginResult:
        """生成知识库内容"""
        pass


class EvaluatorPlugin(BasePlugin):
    """质量评估器插件接口"""
    
    @abstractmethod
    def evaluate(self, content: str, criteria: Dict[str, Any] = None) -> PluginResult:
        """评估内容质量"""
        pass


class PluginRegistry:
    """插件注册表"""
    
    def __init__(self):
        self._plugins: Dict[str, BasePlugin] = {}
        self._configs: Dict[str, PluginConfig] = {}
    
    def register(self, plugin: BasePlugin, config: PluginConfig = None):
        """注册插件"""
        self._plugins[plugin.name] = plugin
        if config:
            self._configs[plugin.name] = config
            plugin.initialize(config)
    
    def get(self, name: str) -> Optional[BasePlugin]:
        """获取插件"""
        return self._plugins.get(name)
    
    def list_plugins(self) -> List[str]:
        """列出所有插件"""
        return list(self._plugins.keys())
    
    def execute(self, name: str, input_data: Dict[str, Any]) -> PluginResult:
        """执行插件"""
        plugin = self._plugins.get(name)
        if not plugin:
            return PluginResult(success=False, error=f"Plugin {name} not found")
        
        if not plugin.validate_input(input_data):
            return PluginResult(success=False, error="Invalid input data")
        
        try:
            return plugin.execute(input_data)
        except Exception as e:
            return PluginResult(success=False, error=str(e))


# 内置插件
class GoScannerPlugin(ScannerPlugin):
    """Go代码扫描器插件"""
    
    @property
    def name(self) -> str:
        return "go_scanner"
    
    def initialize(self, config: PluginConfig) -> bool:
        print(f"Initializing {self.name} plugin...")
        return True
    
    def execute(self, input_data: Dict[str, Any]) -> PluginResult:
        from go_scanner import GoScanner
        scanner = GoScanner()
        repo_path = input_data.get("repo_path", "")
        result = scanner.scan_directory(__import__('pathlib').Path(repo_path))
        return PluginResult(
            success=True,
            data=result.to_dict(),
            metrics={"structs": len(result.structs), "functions": len(result.functions)}
        )
    
    def scan(self, repo_path: str, options: Dict[str, Any] = None) -> PluginResult:
        return self.execute({"repo_path": repo_path, **(options or {})})
    
    def destroy(self) -> None:
        pass


class CommunityEnhancerPlugin(BasePlugin):
    """社区增强器插件"""
    
    @property
    def name(self) -> str:
        return "community_enhancer"
    
    def initialize(self, config: PluginConfig) -> bool:
        return True
    
    def execute(self, input_data: Dict[str, Any]) -> PluginResult:
        from community_enhancer import CommunityEnhancer
        enhancer = CommunityEnhancer()
        nodes = input_data.get("nodes", [])
        edges = input_data.get("edges", [])
        result = enhancer.analyze_communities({"nodes": nodes, "edges": edges, "communities": {}})
        return PluginResult(success=True, data=result)
    
    def destroy(self) -> None:
        pass


# 插件工厂
def create_builtin_plugins() -> PluginRegistry:
    """创建内置插件注册表"""
    registry = PluginRegistry()
    registry.register(GoScannerPlugin())
    registry.register(CommunityEnhancerPlugin())
    return registry
