#!/usr/bin/env python3
"""
统一API接口设计
所有引擎使用统一的IRDocument接口
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class NodeType(Enum):
    """节点类型"""
    STRUCT = "struct"
    FUNCTION = "function"
    ROUTE = "route"
    IMPORT = "import"
    COMMUNITY = "community"
    NODE = "node"
    EDGE = "edge"


class EdgeType(Enum):
    """边类型"""
    DEPENDS_ON = "DEPENDS_ON"
    CALLS = "CALLS"
    CONTAINS = "CONTAINS"
    IMPORTS = "IMPORTS"
    BELONGS_TO = "BELONGS_TO"


@dataclass
class Node:
    """图节点"""
    id: str
    label: str
    node_type: NodeType
    source_file: str = ""
    source_location: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Edge:
    """图边"""
    source: str
    target: str
    edge_type: EdgeType
    confidence: float = 1.0


@dataclass
class IRDocument:
    """统一中间表示文档 - 所有引擎的标准输入输出"""
    
    # 基本信息
    repo_name: str
    repo_path: str
    language: str
    
    # 图谱数据
    nodes: List[Node] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)
    communities: Dict[str, int] = field(default_factory=dict)
    
    # 结构化数据
    structs: List[Dict] = field(default_factory=list)
    functions: List[Dict] = field(default_factory=list)
    routes: List[Dict] = field(default_factory=list)
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "repo_name": self.repo_name,
            "repo_path": self.repo_path,
            "language": self.language,
            "stats": {
                "nodes": len(self.nodes),
                "edges": len(self.edges),
                "structs": len(self.structs),
                "functions": len(self.functions),
                "routes": len(self.routes),
            },
            "nodes": [n.__dict__ for n in self.nodes[:100]],
            "edges": [e.__dict__ for e in self.edges[:200]],
            "communities": self.communities,
        }
    
    def add_node(self, node: Node):
        """添加节点"""
        self.nodes.append(node)
    
    def add_edge(self, edge: Edge):
        """添加边"""
        self.edges.append(edge)
    
    def add_struct(self, struct: Dict):
        """添加结构体"""
        self.structs.append(struct)
    
    def add_function(self, func: Dict):
        """添加函数"""
        self.functions.append(func)
    
    def add_route(self, route: Dict):
        """添加路由"""
        self.routes.append(route)


# 统一API接口
class BaseEngine(ABC):
    """引擎基类 - 所有引擎必须实现此接口"""
    
    @abstractmethod
    def name(self) -> str:
        """引擎名称"""
        pass
    
    @abstractmethod
    def execute(self, input_data: IRDocument) -> IRDocument:
        """执行引擎逻辑"""
        pass
    
    @abstractmethod
    def validate_input(self, input_data: IRDocument) -> bool:
        """验证输入数据"""
        pass


class GraphifyEngine(BaseEngine):
    """Graphify代码图谱分析引擎"""
    
    def name(self) -> str:
        return "graphify"
    
    def execute(self, input_data: IRDocument) -> IRDocument:
        # 调用graphify_analysis
        from graphify_analysis import run_graphify_analysis
        result = run_graphify_analysis(input_data.repo_path)
        
        # 转换结果
        for node in result.get("nodes", []):
            input_data.add_node(Node(
                id=node["id"],
                label=node["label"],
                node_type=NodeType(node.get("type", "node")),
                source_file=node.get("file", ""),
                properties=node.get("properties", {}),
            ))
        
        for edge in result.get("edges", []):
            input_data.add_edge(Edge(
                source=edge["source"],
                target=edge["target"],
                edge_type=EdgeType(edge.get("type", "DEPENDS_ON")),
            ))
        
        return input_data
    
    def validate_input(self, input_data: IRDocument) -> bool:
        return input_data.repo_path and len(input_data.repo_path) > 0


class CommunityEngine(BaseEngine):
    """社区检测引擎"""
    
    def name(self) -> str:
        return "community"
    
    def execute(self, input_data: IRDocument) -> IRDocument:
        from community_enhancer import CommunityEnhancer
        enhancer = CommunityEnhancer()
        
        nodes = [{"id": n.id, "label": n.label} for n in input_data.nodes]
        edges = [{"source": e.source, "target": e.target} for e in input_data.edges]
        
        result = enhancer.analyze_communities({
            "nodes": nodes,
            "edges": edges,
            "communities": {}
        })
        
        input_data.communities = result.get("communities", {})
        return input_data
    
    def validate_input(self, input_data: IRDocument) -> bool:
        return len(input_data.nodes) > 0 and len(input_data.edges) > 0


class PromptEngine(BaseEngine):
    """Prompt生成引擎"""
    
    def name(self) -> str:
        return "prompt"
    
    def execute(self, input_data: IRDocument) -> IRDocument:
        from graphify_analysis import build_compact_prompt
        prompt = build_compact_prompt(input_data)
        input_data.metadata["prompt"] = prompt
        input_data.metadata["prompt_length"] = len(prompt)
        return input_data
    
    def validate_input(self, input_data: IRDocument) -> bool:
        return len(input_data.nodes) > 0


# 引擎工厂
def create_engines() -> List[BaseEngine]:
    """创建所有引擎"""
    return [
        GraphifyEngine(),
        CommunityEngine(),
        PromptEngine(),
    ]


def run_pipeline(repo_path: str, output_dir: str = None) -> IRDocument:
    """运行完整pipeline"""
    # 1. 创建输入文档
    input_doc = IRDocument(
        repo_name=repo_path.split("/")[-1],
        repo_path=repo_path,
        language="go",
    )
    
    # 2. 执行引擎
    engines = create_engines()
    for engine in engines:
        if engine.validate_input(input_doc):
            input_doc = engine.execute(input_doc)
            print(f"  ✅ {engine.name()} engine completed")
        else:
            print(f"  ⏭️  {engine.name()} engine skipped (validation failed)")
    
    return input_doc
