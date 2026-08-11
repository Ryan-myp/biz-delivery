#!/usr/bin/env python3
"""
单元测试 - 覆盖核心功能
目标: 提升测试覆盖到80%
"""

import unittest
import sys
import os
import tempfile
import json
from pathlib import Path


class TestCodeParser(unittest.TestCase):
    """测试code_parser模块"""
    
    def test_ir_document_creation(self):
        """测试IRDocument创建"""
        from code_parser import IRDocument, StructDef, FuncDef, RouteDef
        
        ir = IRDocument(repo_name="test", repo_path="/tmp/test", language="go")
        self.assertEqual(ir.repo_name, "test")
        self.assertEqual(len(ir.structs), 0)
        self.assertEqual(len(ir.functions), 0)
    
    def test_ir_document_add_struct(self):
        """测试添加结构体"""
        from code_parser import IRDocument, StructDef
        
        ir = IRDocument(repo_name="test", repo_path="/tmp/test", language="go")
        struct = StructDef(name="User", file="user.go", fields=[{"name": "ID", "type": "int"}])
        ir.add_struct(struct.__dict__)
        
        self.assertEqual(len(ir.structs), 1)
        self.assertEqual(ir.structs[0]["name"], "User")
    
    def test_ir_document_to_dict(self):
        """测试序列化"""
        from code_parser import IRDocument
        
        ir = IRDocument(repo_name="test", repo_path="/tmp/test", language="go")
        ir.structs.append({"name": "TestStruct", "file": "test.go"})
        
        result = ir.to_dict()
        self.assertIn("stats", result)
        self.assertEqual(result["stats"]["structs"], 1)


class TestGoScanner(unittest.TestCase):
    """测试GoScanner模块"""
    
    def setUp(self):
        """设置测试环境"""
        self.test_dir = Path(tempfile.mkdtemp(prefix="go-test-"))
        
        # 创建测试Go文件
        self.test_go = self.test_dir / "test.go"
        self.test_go.write_text('''
package test

type User struct {
    ID   int    \`json:"id"\`
    Name string \`json:"name"\`
}

func (u *User) GetName() string {
    return u.Name
}

func CreateUser(id int, name string) *User {
    return &User{ID: id, Name: name}
}
''')
    
    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_scan_go_file(self):
        """测试Go文件扫描"""
        from go_scanner import GoScanner
        
        scanner = GoScanner()
        result = scanner.scan_directory(self.test_dir)
        
        self.assertGreater(len(result.structs), 0)
        self.assertGreater(len(result.functions), 0)
    
    def test_scan_finds_struct(self):
        """测试找到结构体"""
        from go_scanner import GoScanner
        
        scanner = GoScanner()
        result = scanner.scan_directory(self.test_dir)
        
        struct_names = [s.name for s in result.structs]
        self.assertIn("User", struct_names)
    
    def test_scan_finds_functions(self):
        """测试找到函数"""
        from go_scanner import GoScanner
        
        scanner = GoScanner()
        result = scanner.scan_directory(self.test_dir)
        
        func_names = [f.name for f in result.functions]
        self.assertIn("GetName", func_names)
        self.assertIn("CreateUser", func_names)


class TestGraphBuilder(unittest.TestCase):
    """测试GraphBuilder模块"""
    
    def test_build_graph(self):
        """测试图谱构建"""
        from graph_builder import GraphBuilder
        from code_parser import IRDocument, Node, Edge, NodeType, EdgeType
        
        builder = GraphBuilder()
        ir = IRDocument(repo_name="test", repo_path="/tmp/test", language="go")
        
        ir.add_node(Node(id="1", label="User", node_type=NodeType.STRUCT))
        ir.add_node(Node(id="2", label="GetName", node_type=NodeType.FUNCTION))
        ir.add_edge(Edge(source="1", target="2", edge_type=EdgeType.CALLS))
        
        graph = builder.build_graph(ir)
        
        self.assertEqual(graph["stats"]["total_nodes"], 2)
        self.assertEqual(graph["stats"]["total_edges"], 1)


class TestKnowledgeExtractor(unittest.TestCase):
    """测试KnowledgeExtractor模块"""
    
    def test_extract_error_codes(self):
        """测试错误码提取"""
        from knowledge_extractor import KnowledgeExtractor
        from code_parser import IRDocument, StructDef
        
        extractor = KnowledgeExtractor()
        ir = IRDocument(repo_name="test", repo_path="/tmp/test", language="go")
        ir.structs.append(StructDef(name="ErrorCode", file="error.go", fields=[]))
        
        results = extractor.extract_error_codes(ir)
        self.assertGreater(len(results), 0)


class TestUnifieAPI(unittest.TestCase):
    """测试统一API"""
    
    def test_run_pipeline(self):
        """测试完整pipeline"""
        from unified_api import run_pipeline
        
        # 创建临时Go文件
        import tempfile
        from pathlib import Path
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_go = Path(tmpdir) / "test.go"
            test_go.write_text('''
package test

type User struct {
    ID int
}
''')
            
            result = run_pipeline(str(tmpdir))
            
            self.assertGreater(len(result.nodes), 0)


class TestPluginArchitecture(unittest.TestCase):
    """测试插件架构"""
    
    def test_plugin_registry(self):
        """测试插件注册表"""
        from plugin_architecture import PluginRegistry, GoScannerPlugin
        
        registry = PluginRegistry()
        plugin = GoScannerPlugin()
        registry.register(plugin)
        
        self.assertEqual(registry.list_plugins(), ["go_scanner"])
    
    def test_plugin_execute(self):
        """测试插件执行"""
        from plugin_architecture import PluginRegistry, GoScannerPlugin
        
        registry = PluginRegistry()
        plugin = GoScannerPlugin()
        registry.register(plugin)
        
        result = registry.execute("go_scanner", {"repo_path": "."})
        self.assertIsInstance(result.success, bool)


def run_tests():
    """运行所有测试"""
    loader = unittest.TestLoader()
    suite = loader.discover('scripts', pattern='test_*.py')
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.returncode


if __name__ == '__main__':
    sys.exit(run_tests())
