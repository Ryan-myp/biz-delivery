#!/usr/bin/env python3
"""
Knowledge → Wiki Ingest 脚本
将 ryan-personal-knowledge/knowledge/ 下的 .md 文件自动 ingested 到
biz-delivery/wiki-engine/wiki/，生成 frontmatter + wikilinks + index.md

用法:
    python3 kb_to_wiki.py                         # dry-run，预览
    python3 kb_to_wiki.py --force                 # 执行 ingest
    python3 kb_to_wiki.py --dry-run               # 预览模式（默认）
    python3 kb_to_wiki.py --kb-dir <path>          # 自定义 KB 目录
    python3 kb_to_wiki.py --wiki-dir <path>        # 自定义 Wiki 目录
    python3 kb_to_wiki.py --skip <pattern>         # 跳过匹配文件
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────

KB_ROOT = Path(__file__).parent.parent / "ryan-personal-knowledge" / "knowledge"
WIKI_ROOT = Path(__file__).parent / "wiki"

# 跳过模式
SKIP_PATTERNS = {"README.md", "README", "index.md", "log.md"}

# 类型启发式分类关键词
ENTITY_KEYWORDS = ['person', 'product', 'service', 'tool', 'platform', 'api', 
                   '公司', '产品', '服务', '工具', '平台', '系统']
CONCEPT_KEYWORDS = ['concept', 'method', 'pattern', '架构', '原理', '模式', 
                    '概念', '方法', '设计模式', '源码', '深度', '深入', '核心']

# 目录 → wiki 子目录映射
DIR_TO_WIKI_SUBDIR = {
    "agent-ai": "concepts",
    "ad-ads": "concepts",
    "fullstack": "concepts",
    "middleware": "concepts",
    "architecture": "concepts",
    "architecture-patterns": "comparisons",
    "tools": "entities",
    "growth-plan": "concepts",
    "前沿": "concepts",
    "advertising": "concepts",
}

# ──────────────────────────────────────────────
# Parsing
# ──────────────────────────────────────────────

TAG_RE = re.compile(r'#([-\w\u4e00-\u9fff][-\w\u4e00-\u9fff_]*)')
FRONTMATTER_RE = re.compile(r'^---\n(.*?)\n---', re.DOTALL)
BACKTICK_TAG_RE = re.compile(r'`(#?[\w\u4e00-\u9fff]+)`')
HEADLINE_RE = re.compile(r'^#{1,6}\s+(.+)$', re.MULTILINE)


def extract_meta(content: str) -> Dict[str, Any]:
    """从 markdown 提取 meta 信息（标签、标题、日期等）"""
    tags = []
    headings = []
    created = ""
    
    # 先尝试 YAML frontmatter
    fm_match = FRONTMATTER_RE.search(content)
    if fm_match:
        try:
            fm = json.loads(fm_match.group(1))
            tags = [str(t) for t in fm.get('tags', [])]
            created = fm.get('created', '')
        except json.JSONDecodeError:
            pass
    
    # 尝试 > 标签: `#tag1` `#tag2` 格式（非 YAML frontmatter 格式）
    if not tags:
        meta_tags = BACKTICK_TAG_RE.findall(content)
        if meta_tags:
            tags = [t.lstrip('#') for t in meta_tags[:10]]
    
    # 也扫描 #tag 格式
    if not tags:
        tags = list(set(TAG_RE.findall(content)))[:10]
    
    headings = HEADLINE_RE.findall(content)
    
    # 提取创建日期
    if not created:
        date_match = re.search(r'(?:创建日期|date|created)\s*[:：]?\s*(\d{4}[-/]\d{2}[-/]\d{2}|\d{8})', content, re.IGNORECASE)
        if date_match:
            created = date_match.group(1).replace('/', '-')
    
    return {
        "title": headings[0] if headings else Path(content).stem,
        "tags": tags,
        "headings": headings[:15],
        "created": created,
        "word_count": len(content.split()),
    }


def classify_page(title: str, tags: List[str], headings: List[str], content: str) -> str:
    """分类为 entity / concept / comparison / query"""
    text = f"{title} {' '.join(tags)} {' '.join(headings)} {content[:1000]}".lower()
    
    for kw in ENTITY_KEYWORDS:
        if kw in text:
            return "entity"
    
    for kw in CONCEPT_KEYWORDS:
        if kw in text:
            return "concept"
    
    # 默认 concept
    return "concept"


# ──────────────────────────────────────────────
# Wikilink resolution
# ──────────────────────────────────────────────

def title_to_slug(title: str) -> str:
    """标题 → 文件 slug（截断+清理）"""
    slug = title.lower()
    # 移除 markdown 标记
    slug = re.sub(r'[#*_`]', '', slug)
    # 移除非字母数字字符（保留中文、连字符）
    slug = re.sub(r'[^\w\u4e00-\u9fff-]', '-', slug)
    slug = slug.strip('-')
    # 截断到 60 字符
    if len(slug) > 60:
        slug = slug[:55] + '...'
    return slug or "untitled"


def infer_wikilinks(page_meta: Dict, all_titles: Set[str], max_links: int = 5) -> List[str]:
    """根据标题和标签推断 wikilinks"""
    links = []
    
    # 优先使用 tags 作为 wikilinks（clean tag，非 heading）
    for tag in page_meta.get("tags", [])[:max_links]:
        clean_tag = tag.lstrip('#')
        if clean_tag and 2 < len(clean_tag) < 30:
            links.append(clean_tag)
    
    # 限制最多 max_links 个
    return list(dict.fromkeys(links))[:max_links]


# ──────────────────────────────────────────────
# Build page content with frontmatter
# ──────────────────────────────────────────────

def build_wiki_page(meta: Dict, content: str, wikilinks: List[str]) -> str:
    """构建带 frontmatter 的 wiki 页面"""
    fm = {
        "title": meta["title"],
        "created": meta.get("created", "2026-06-09"),
        "updated": "2026-06-09",
        "type": meta.get("type", "concept"),
        "tags": meta.get("tags", []),
    }
    
    fm_lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            fm_lines.append(f"{k}: [{', '.join(v)}]")
        else:
            fm_lines.append(f"{k}: {v}")
    fm_lines.append("---")
    
    frontmatter = "\n".join(fm_lines)
    
    # 追加 wikilinks
    if wikilinks:
        link_block = "\n\n### 相关页面\n" + "\n".join(f"- [[{l}]]" for l in wikilinks)
        body = content.rstrip() + link_block
    else:
        body = content.rstrip()
    
    return frontmatter + "\n\n" + body


# ──────────────────────────────────────────────
# Main logic
# ──────────────────────────────────────────────

def scan_kb(kb_root: Path) -> List[Dict]:
    """扫描知识库，返回文档列表"""
    docs = []
    
    for md_file in sorted(kb_root.rglob("*.md")):
        rel = md_file.relative_to(kb_root)
        
        # 跳过
        if md_file.name in SKIP_PATTERNS:
            continue
        if parts := rel.parts:
            if "knowledge-search" in parts or ".git" in parts:
                continue
            if "ryan-personal-knowledge" in parts and parts.index("ryan-personal-knowledge") > 0:
                continue
        
        try:
            content = md_file.read_text(encoding="utf-8")
            if len(content.split()) < 10:  # 太短跳过
                continue
            
            meta = extract_meta(content)
            meta["type"] = classify_page(
                meta["title"], meta["tags"], meta["headings"], content
            )
            meta["kb_path"] = str(md_file)
            meta["kb_rel"] = str(rel)
            meta["kb_dir"] = rel.parts[0] if rel.parts else ""
            docs.append(meta)
        except Exception as e:
            print(f"  [WARN] 跳过 {rel}: {e}", file=sys.stderr)
    
    return docs


def ingest(kb_root: Path, wiki_root: Path, docs: List[Dict], 
           force: bool = False, dry_run: bool = True) -> Dict[str, Any]:
    """
    执行 ingest：
    1. 为每个文档添加 frontmatter + wikilinks
    2. 写入 wiki/ 目录
    3. 更新 index.md
    4. 更新 log.md
    """
    results = {"created": [], "updated": [], "skipped": 0}
    
    # 预收集所有标题
    all_titles = set()
    for d in docs:
        slug = title_to_slug(d["title"])
        all_titles.add(slug)
    
    # 先批量处理所有文档（用于 wikilinks 互指）
    doc_slugs = {}
    doc_wikilinks = {}
    for d in docs:
        slug = title_to_slug(d["title"])
        doc_slugs[str(d["kb_path"])] = slug
        wikilinks = infer_wikilinks(d, all_titles)
        doc_wikilinks[str(d["kb_path"])] = wikilinks
    
    # 写入页面
    for d in docs:
        kb_path = d["kb_path"]
        slug = doc_slugs[kb_path]
        wikilinks = doc_wikilinks[kb_path]
        
        # 读取原文
        content = Path(kb_path).read_text(encoding="utf-8")
        
        # 分类
        page_type = d["type"]
        subdir = DIR_TO_WIKI_SUBDIR.get(d["kb_dir"], "concepts")
        
        # 目标路径
        page_slug = f"{slug}.md"
        dest = wiki_root / subdir / page_slug
        
        exists = dest.exists()
        
        if exists and not force:
            print(f"  ⏭️  跳过 (已存在): {dest.relative_to(wiki_root.parent)}")
            results["skipped"] += 1
            continue
        
        # 构建页面
        wiki_content = build_wiki_page(d, content, wikilinks)
        
        # 写入
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(wiki_content, encoding="utf-8")
        
        if exists:
            results["updated"].append(str(dest.relative_to(wiki_root.parent)))
            print(f"  🔄 更新: {dest.relative_to(wiki_root.parent)}")
        else:
            results["created"].append(str(dest.relative_to(wiki_root.parent)))
            print(f"  ✅ 创建: {dest.relative_to(wiki_root.parent)} ({page_type})")
    
    # 更新 index.md
    index_lines = ["# Wiki Index\n", '> Auto-generated from knowledge/\n\n']
    sections = {
        "Entities": [],
        "Concepts": [],
        "Comparisons": [],
    }
    
    for d in docs:
        title = d["title"]
        slug = title_to_slug(title)
        page_type = d["type"]
        heading = d["headings"][0] if d["headings"] else title
        section = page_type if page_type in sections else "Concepts"
        sections[section].append(f"- [[{title}]] — {heading}")
    
    for section_name, entries in sections.items():
        if entries:
            index_lines.append(f"\n## {section_name}\n")
            index_lines.extend(sorted(entries))
    
    index_path = wiki_root / "index.md"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text("".join(index_lines), encoding="utf-8")
    
    # 更新 log.md
    log_path = wiki_root / "log.md"
    log_content = log_path.read_text(encoding="utf-8") if log_path.exists() else "# Wiki Log\n\n"
    created_count = len(results["created"])
    updated_count = len(results["updated"])
    entry = (f"## [2026-06-09] kb_to_wiki ingest | "
             f"{created_count} created, {updated_count} updated\n")
    log_path.write_text(log_content + "\n" + entry, encoding="utf-8")
    
    return results


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="KB → Wiki Ingest: 将 knowledge/ .md 文件转为 wiki 页面"
    )
    parser.add_argument("--kb-dir", default=str(KB_ROOT), help="知识库根目录")
    parser.add_argument("--wiki-dir", default=str(WIKI_ROOT), help="Wiki 根目录")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的页面")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="预览模式（默认）")
    parser.add_argument("--execute", action="store_true",
                        help="执行 ingest")

    args = parser.parse_args()
    
    kb_root = Path(args.kb_dir)
    wiki_root = Path(args.wiki_dir)
    force = args.force
    dry_run = not args.execute

    print(f"📦 KB: {kb_root}")
    print(f"📚 Wiki: {wiki_root}")
    print(f"{'[DRY RUN]' if dry_run else '[EXECUTE]'}")
    print()

    # Scan
    print("🔍 扫描知识库...")
    docs = scan_kb(kb_root)
    print(f"   找到 {len(docs)} 个文档\n")

    if not docs:
        print("没有可 ingested 的文档。")
        return

    # Print preview
    print("📋 预览:")
    for d in docs:
        subdir = DIR_TO_WIKI_SUBDIR.get(d["kb_dir"], "concepts")
        slug = title_to_slug(d["title"])
        wikilinks = infer_wikilinks(d, set(title_to_slug(dd["title"]) for dd in docs))[:3]
        print(f"  [{d['type']}] {d['kb_rel']}")
        print(f"         → {subdir}/{slug}.md")
        if wikilinks:
            print(f"         wikilinks: {', '.join(wikilinks)}")
    print()

    # Execute
    if dry_run:
        print("这是预览模式。使用 --execute 执行 ingest。")
        print(f"将会创建/更新 {len(docs)} 个 wiki 页面。")
    else:
        results = ingest(kb_root, wiki_root, docs, force=force, dry_run=False)
        print(f"\n✅ 完成: {len(results['created'])} 创建, "
              f"{len(results['updated'])} 更新, "
              f"{results['skipped']} 跳过")


if __name__ == "__main__":
    main()
