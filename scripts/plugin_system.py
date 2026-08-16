"""
Plugin System - 领域插件注册机制
支持动态加载领域插件，扩展专家系统能力

核心功能:
  1. 插件注册表
  2. 插件生命周期管理
  3. 插件依赖解析
  4. 插件版本控制
"""
import importlib
import inspect
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Type, Callable
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PluginMetadata:
    """插件元数据"""
    plugin_id: str
    name: str
    version: str
    description: str
    author: str
    domain: str
    dependencies: List[str] = field(default_factory=list)
    entry_point: str = ""
    enabled: bool = True


class PluginManager:
    """插件管理器"""

    PLUGIN_REGISTRY_PATH = Path('./plugins/registry.json')
    PLUGIN_DIR = Path('./plugins')

    def __init__(self):
        self.plugins: Dict[str, PluginMetadata] = {}
        self.plugin_classes: Dict[str, Type] = {}
        self.plugin_instances: Dict[str, Any] = {}
        self._load_registry()

    def _load_registry(self):
        """加载插件注册表"""
        if self.PLUGIN_REGISTRY_PATH.exists():
            try:
                data = json.loads(self.PLUGIN_REGISTRY_PATH.read_text())
                for pid, meta in data.get('plugins', {}).items():
                    self.plugins[pid] = PluginMetadata(**meta)
            except:
                pass

    def _save_registry(self):
        """保存插件注册表"""
        self.PLUGIN_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {
            'plugins': {pid: vars(meta) for pid, meta in self.plugins.items()},
            'updated_at': datetime.now().isoformat(),
        }
        self.PLUGIN_REGISTRY_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def register(self, plugin_id: str, metadata: PluginMetadata,
                 class_factory: Optional[Callable] = None):
        """注册插件"""
        self.plugins[plugin_id] = metadata
        if class_factory:
            self.plugin_classes[plugin_id] = class_factory
        self._save_registry()
        print(f"✅ 插件已注册: {plugin_id} v{metadata.version}")

    def load_plugin(self, plugin_id: str) -> Optional[Any]:
        """加载插件实例"""
        if plugin_id not in self.plugins:
            return None

        meta = self.plugins[plugin_id]
        if not meta.enabled:
            return None

        # 检查依赖
        if not self._check_dependencies(plugin_id):
            return None

        # 创建实例
        if plugin_id in self.plugin_instances:
            return self.plugin_instances[plugin_id]

        if plugin_id in self.plugin_classes:
            try:
                instance = self.plugin_classes[plugin_id]()
                self.plugin_instances[plugin_id] = instance
                print(f"🔌 插件已加载: {meta.name}")
                return instance
            except Exception as e:
                print(f"❌ 插件加载失败: {plugin_id} - {e}")
                return None

        return None

    def _check_dependencies(self, plugin_id: str) -> bool:
        """检查依赖"""
        meta = self.plugins.get(plugin_id)
        if not meta:
            return False

        for dep in meta.dependencies:
            if dep not in self.plugins:
                print(f"⚠️ 缺少依赖: {dep} (required by {plugin_id})")
                return False
            if not self.plugins[dep].enabled:
                print(f"⚠️ 依赖未启用: {dep}")
                return False
        return True

    def get_plugin(self, plugin_id: str) -> Optional[Any]:
        """获取插件实例"""
        return self.load_plugin(plugin_id)

    def list_plugins(self, enabled_only: bool = False) -> List[Dict]:
        """列出所有插件"""
        result = []
        for pid, meta in self.plugins.items():
            if enabled_only and not meta.enabled:
                continue
            result.append({
                'id': pid,
                'name': meta.name,
                'version': meta.version,
                'domain': meta.domain,
                'enabled': meta.enabled,
                'dependencies': meta.dependencies,
            })
        return result

    def enable_plugin(self, plugin_id: str):
        """启用插件"""
        if plugin_id in self.plugins:
            self.plugins[plugin_id].enabled = True
            self._save_registry()

    def disable_plugin(self, plugin_id: str):
        """禁用插件"""
        if plugin_id in self.plugins:
            self.plugins[plugin_id].enabled = False
            self._save_registry()


# 预置插件工厂
def create_ad_plugin():
    """广告领域插件"""
    class AdPlugin:
        def __init__(self):
            self.name = "广告领域插件"
            self.rules = {
                'bid_optimization': '竞价引擎优化规则',
                'budget_tracking': '预算追踪规则',
                'anti_fraud': '反作弊检测规则',
            }

        def get_rules(self):
            return self.rules
    return AdPlugin()


def create_agent_plugin():
    """Agent领域插件"""
    class AgentPlugin:
        def __init__(self):
            self.name = "Agent领域插件"
            self.capabilities = ['reAct', 'planner', 'memory', 'tools']

        def get_capabilities(self):
            return self.capabilities
    return AgentPlugin()


# 注册预置插件
def init_builtin_plugins(manager: PluginManager):
    """初始化内置插件"""
    from scripts.ai_decision_engine import AIDecisionEngine

    # AI决策引擎作为插件
    manager.register(
        plugin_id='ai_decision_engine',
        metadata=PluginMetadata(
            plugin_id='ai_decision_engine',
            name='AI决策引擎',
            version='1.0.0',
            description='基于知识库和案例的智能决策支持',
            author='biz-delivery',
            domain='all',
        ),
        class_factory=lambda: AIDecisionEngine(),
    )

    # 广告插件
    manager.register(
        plugin_id='ad_plugin',
        metadata=PluginMetadata(
            plugin_id='ad_plugin',
            name='广告领域插件',
            version='1.0.0',
            description='广告竞价相关规则和最佳实践',
            author='biz-delivery',
            domain='advertising',
        ),
        class_factory=create_ad_plugin,
    )

    # Agent插件
    manager.register(
        plugin_id='agent_plugin',
        metadata=PluginMetadata(
            plugin_id='agent_plugin',
            name='Agent领域插件',
            version='1.0.0',
            description='Agent框架相关规则和最佳实践',
            author='biz-delivery',
            domain='agent',
        ),
        class_factory=create_agent_plugin,
    )


# 单例
_plugin_manager = None

def get_plugin_manager() -> PluginManager:
    """获取插件管理器单例"""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
        init_builtin_plugins(_plugin_manager)
    return _plugin_manager


if __name__ == '__main__':
    import sys
    manager = get_plugin_manager()

    print("=" * 60)
    print("🔌 插件系统测试")
    print("=" * 60)

    # 列出所有插件
    print("\n【已注册插件】")
    for p in manager.list_plugins():
        status = "✅" if p['enabled'] else "❌"
        print(f"  {status} {p['id']}: {p['name']} v{p['version']} ({p['domain']})")

    # 加载插件
    print("\n【加载插件】")
    ad_plugin = manager.get_plugin('ad_plugin')
    if ad_plugin:
        print(f"  ✅ 广告插件已加载: {ad_plugin.name}")
        print(f"     规则: {list(ad_plugin.get_rules().keys())}")

    agent_plugin = manager.get_plugin('agent_plugin')
    if agent_plugin:
        print(f"  ✅ Agent插件已加载: {agent_plugin.name}")
        print(f"     能力: {agent_plugin.get_capabilities()}")

    ai_plugin = manager.get_plugin('ai_decision_engine')
    if ai_plugin:
        print(f"  ✅ AI决策引擎已加载")

    print("\n" + "=" * 60)
PYEOF