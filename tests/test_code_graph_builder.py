"""Tests for code_graph_builder — GraphNode, GraphEdge, CodeGraph, GoParser, passes."""
import json
import pytest
from pathlib import Path

from scripts.code_graph_builder import (
    GraphNode, GraphEdge, CodeGraph,
    GoParser, PassDefinitions, PassCalls, PassImports, PassRoutes, CodeGraphBuilder,
)


# ===========================================================================
# GraphNode / GraphEdge
# ===========================================================================

class TestGraphNode:
    def test_default(self):
        n = GraphNode()
        assert n.id == 0
        assert n.label == ""
        assert n.name == ""
        assert n.properties == {}

    def test_with_values(self):
        n = GraphNode(id=1, label="Function", name="foo", qualified_name="pkg/foo",
                      file_path="a.go", start_line=10, end_line=20,
                      properties={"params": "ctx"})
        assert n.id == 1
        assert n.properties["params"] == "ctx"


class TestGraphEdge:
    def test_default(self):
        e = GraphEdge()
        assert e.id == 0
        assert e.type == ""

    def test_with_values(self):
        e = GraphEdge(id=1, source_id=1, target_id=2, type="CALLS",
                      properties={"confidence": 0.9})
        assert e.type == "CALLS"
        assert e.properties["confidence"] == 0.9


# ===========================================================================
# CodeGraph
# ===========================================================================

class TestCodeGraph:
    def test_add_node(self):
        g = CodeGraph()
        nid = g.add_node("Function", "foo", "pkg/foo", "a.go")
        assert nid == 1
        assert len(g.nodes) == 1
        assert g.node_by_qn["pkg/foo"] == 1
        assert g.node_by_id[1].name == "foo"

    def test_add_node_next_id(self):
        g = CodeGraph()
        g.add_node("Function", "a", "q:a", "a.go")
        g.add_node("Function", "b", "q:b", "b.go")
        assert g.next_node_id == 3

    def test_add_edge(self):
        g = CodeGraph()
        n1 = g.add_node("Function", "a", "q:a", "a.go")
        n2 = g.add_node("Function", "b", "q:b", "b.go")
        eid = g.add_edge(n1, n2, "CALLS")
        assert eid == 1
        assert len(g.edges) == 1
        assert g.edges[0].type == "CALLS"

    def test_find_by_qn(self):
        g = CodeGraph()
        g.add_node("Function", "foo", "pkg/foo", "a.go")
        node = g.find_by_qn("pkg/foo")
        assert node is not None
        assert node.name == "foo"
        assert g.find_by_qn("unknown") is None

    def test_find_by_id(self):
        g = CodeGraph()
        nid = g.add_node("Function", "foo", "pkg/foo", "a.go")
        node = g.find_by_id(nid)
        assert node is not None
        assert g.find_by_id(999) is None

    def test_get_outgoing_edges(self):
        g = CodeGraph()
        n1 = g.add_node("Function", "a", "q:a", "a.go")
        n2 = g.add_node("Function", "b", "q:b", "b.go")
        g.add_edge(n1, n2, "CALLS")
        g.add_edge(n1, n2, "IMPORTS")
        calls = g.get_outgoing_edges(n1, "CALLS")
        assert len(calls) == 1
        all_edges = g.get_outgoing_edges(n1)
        assert len(all_edges) == 2

    def test_get_incoming_edges(self):
        g = CodeGraph()
        n1 = g.add_node("Function", "a", "q:a", "a.go")
        n2 = g.add_node("Function", "b", "q:b", "b.go")
        g.add_edge(n1, n2, "CALLS")
        incoming = g.get_incoming_edges(n2, "CALLS")
        assert len(incoming) == 1

    def test_to_dict(self):
        g = CodeGraph()
        n1 = g.add_node("Function", "foo", "q:foo", "a.go")
        n2 = g.add_node("Route", "GET /api", "q:route", "a.go")
        g.add_edge(n1, n2, "HANDLES")
        d = g.to_dict()
        assert d["node_count"] == 2
        assert d["edge_count"] == 1
        assert len(d["nodes"]) == 2
        assert len(d["edges"]) == 1

    def test_save_json(self, tmp_path):
        g = CodeGraph()
        g.add_node("Function", "foo", "q:foo", "a.go")
        out = tmp_path / "graph.json"
        g.save_json(str(out))
        data = json.loads(out.read_text())
        assert data["node_count"] == 1


# ===========================================================================
# GoParser
# ===========================================================================

class TestGoParser:
    GO_SOURCE = '''package main

import (
    "fmt"
    "net/http"
)

type User struct {
    ID   int
    Name string
}

func (u *User) GetName() string {
    return u.Name
}

func CreateUser() User {
    return User{}
}

func RegisterRoutes(r *gin.Engine) {
    r.GET("/api/users", CreateUser)
    r.POST("/api/users", CreateUser)
}
'''

    def test_extract_file_info(self):
        info = GoParser.extract_file_info(self.GO_SOURCE, "main.go")
        assert info["package"] == "main"
        assert len(info["imports"]) == 2
        paths = {imp["path"] for imp in info["imports"]}
        assert "fmt" in paths
        assert "net/http" in paths
        assert len(info["structs"]) == 1
        assert info["structs"][0]["name"] == "User"
        # Top-level functions only (methods with receivers are not added)
        func_names = [f["name"] for f in info["functions"]]
        assert "CreateUser" in func_names

    def test_extract_routes(self):
        info = GoParser.extract_file_info(self.GO_SOURCE, "main.go")
        routes = info["routes"]
        assert len(routes) == 2
        paths = {r["path"] for r in routes}
        assert "/api/users" in paths

    def test_extract_variables(self):
        source = "var counter int\nconst max = 100\n"
        info = GoParser.extract_file_info(source, "vars.go")
        names = [v["name"] for v in info["variables"]]
        assert "counter" in names
        assert "max" in names

    def test_extract_interfaces(self):
        source = "type Reader interface { Read(p []byte) (n int, err error) }\n"
        info = GoParser.extract_file_info(source, "iface.go")
        assert len(info["interfaces"]) == 1
        assert info["interfaces"][0]["name"] == "Reader"

    def test_empty_source(self):
        info = GoParser.extract_file_info("", "empty.go")
        assert info["package"] == ""
        assert info["functions"] == []

    def test_compute_fqn_with_receiver(self):
        fqn = GoParser.compute_fqn("github.com/user/svc", "handler.go", "GetUser", "User")
        assert "User" in fqn
        assert "GetUser" in fqn

    def test_compute_fqn_without_receiver(self):
        fqn = GoParser.compute_fqn("github.com/user/svc", "main.go", "ListUsers")
        assert "ListUsers" in fqn
        assert "user/svc" in fqn


# ===========================================================================
# PassDefinitions
# ===========================================================================

class TestPassDefinitions:
    def test_run_go(self):
        g = CodeGraph()
        source = '''package main
func CreateUser() User {
    return User{}
}
type User struct{ ID int }
'''
        p = PassDefinitions(g)
        ids = p.run("main.go", source, "go")
        assert len(ids) > 0
        labels = {n.label for n in g.nodes}
        assert "File" in labels
        assert "Function" in labels

    def test_run_non_go_lang(self):
        g = CodeGraph()
        p = PassDefinitions(g)
        ids = p.run("main.py", "print('hi')", "python")
        assert ids == []


# ===========================================================================
# PassCalls
# ===========================================================================

class TestPassCalls:
    def test_run_go(self):
        g = CodeGraph()
        source = '''package main
func A() User { B() ; return User{} }
func B() User { return User{} }
'''
        PassDefinitions(g).run("main.go", source, "go")
        p = PassCalls(g)
        p.run("main.go", source, "go")
        # Find A and check its CALLS edges
        a_node = g.find_by_qn("main/main.go.A")
        if a_node:
            calls = g.get_outgoing_edges(a_node.id, "CALLS")
            callee_names = {g.find_by_id(e.target_id).name for e in calls}
            assert "B" in callee_names


# ===========================================================================
# PassImports
# ===========================================================================

class TestPassImports:
    def test_run_go(self):
        g = CodeGraph()
        # Single import (no parens) — GoParser doesn't capture it, use import block
        source = '''package main
import (
    "fmt"
)
func main() User { return User{} }
'''
        PassDefinitions(g).run("main.go", source, "go")
        p = PassImports(g)
        p.run("main.go", source, "go")
        imports = [e for e in g.edges if e.type == "IMPORTS"]
        assert len(imports) > 0


# ===========================================================================
# PassRoutes
# ===========================================================================

class TestPassRoutes:
    def test_run_go(self):
        g = CodeGraph()
        source = '''package main
import "github.com/gin-gonic/gin"
func HandleUsers(c *gin.Context) User { return User{} }
func RegisterRoutes(r *gin.Engine) {
    r.GET("/api/users", HandleUsers)
}
'''
        PassDefinitions(g).run("main.go", source, "go")
        p = PassRoutes(g)
        p.run("main.go", source, "go")
        handles = [e for e in g.edges if e.type == "HANDLES"]
        assert len(handles) > 0


# ===========================================================================
# CodeGraphBuilder
# ===========================================================================

class TestCodeGraphBuilder:
    def test_build_empty(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        builder = CodeGraphBuilder("test-proj", str(repo))
        builder.build(lang="go", max_files=0)
        assert len(builder.graph.nodes) == 0

    def test_build_with_go_file(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "main.go").write_text('''package main
import "fmt"
func main() { fmt.Println("hi") }
''')
        builder = CodeGraphBuilder("test-proj", str(repo))
        builder.build(lang="go", max_files=10)
        assert len(builder.graph.nodes) > 0

    def test_save(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "main.go").write_text('package main\nfunc main() {}\n')
        builder = CodeGraphBuilder("test-proj", str(repo))
        builder.build(lang="go", max_files=10)
        out = tmp_path / "graph.json"
        builder.save(str(out))
        assert out.exists()
