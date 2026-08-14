#!/usr/bin/env python3
"""通用架构模式检测器 — 支持 Go/Python/Java 三种语言.

检测 7 类架构模式:
1. 状态机 - 状态常量 + 转换逻辑
2. Redis 锁 - 分布式锁模式
3. 重试机制 - retry/backoff/sleep
4. Kafka/消息队列 - Producer/Consumer
5. 幂等性 - CheckConfirm/分布式锁
6. 任务组 - 批量操作生命周期
7. 枚举/常量 - 字段合法取值范围
"""

import re
from pathlib import Path
from typing import Dict, List, Set, Tuple


# ── 语言模式定义 ────────────────────────────────────────────────

LANGUAGE_PATTERNS = {
    "go": {
        "state_keywords": r'\b(?:State|Status|TaskStatus|OpsStatus)\b',
        "redis_patterns": [
            r'\b(?:DeleteKey|Del|Unlock|LockKey|SetNX|RedisMutex)\b',
            r'\bredis\.(?:Get|Set|Del|Lock|Unlock)\b',
        ],
        "retry_patterns": [
            r'\bretry\b', r'\bbackoff\b', r'\bsleep\b.*time',
            r'\bRetryAfter\b', r'\bMaxRetries\b',
        ],
        "kafka_patterns": [
            r'\bKafkaProducer\b', r'\bKafkaConsumer\b',
            r'\bProducerGroup\b', r'\bConsumerGroup\b',
            r'\bsarama\.\w+', r'\bkafka\.\w+',
        ],
        "idempotency_patterns": [
            r'\bCheckConfirm\b', r'\bIsProcessed\b',
            r'\bidempotent\b', r'\bAlreadyExists\b',
        ],
        "task_group_patterns": [
            r'\bCreateTaskGroup\b', r'\bTaskGroup\b',
            r'\bCallbackFunc\b', r'\bRunFunc\b',
        ],
        "enum_pattern": r'const\s*\([^)]+\)',
    },
    "python": {
        "state_keywords": r'\b(?:State|Status|STAGE|STEP)\b',
        "redis_patterns": [
            r'\bredis\.(?:get|set|delete|incr|expire)\b',
            r'\bRLock\b', r'\bLock\b',
            r'\bsetnx\b', r'\bunlock\b',
        ],
        "retry_patterns": [
            r'\bretry\b', r'\bbackoff\b', r'\bsleep\b',
            r'\bmax_retries\b', r'\bRetry\b',
        ],
        "kafka_patterns": [
            r'\bKafkaConsumer\b', r'\bKafkaProducer\b',
            r'\b confluent_kafka\b', r'\bbroker\b',
            r'\bconsume\b.*kafka', r'\bproduce\b.*kafka',
        ],
        "idempotency_patterns": [
            r'\bidempotent\b', r'\balready_processed\b',
            r'\bcheck_exist\b', r'\bunique_constraint\b',
        ],
        "task_group_patterns": [
            r'\bTaskGroup\b', r'\bcelery\b',
            r'\bchain\b', r'\bgroup\b', r'\bchord\b',
        ],
        "enum_pattern": r'(?:class\s+\w+Enum|Enum\s*\(|@enumerated)',
    },
    "java": {
        "state_keywords": r'\b(?:State|Status|StateEnum|StatusEnum)\b',
        "redis_patterns": [
            r'\bJedis\b', r'\bRedisTemplate\b',
            r'\bredisTemplate\.\w+\b',
            r'\b@Cacheable\b', r'\b@CacheEvict\b',
        ],
        "retry_patterns": [
            r'\bretry\b', r'\bBackoff\b',
            r'\bRetryTemplate\b', r'\bmaxAttempts\b',
        ],
        "kafka_patterns": [
            r'\bKafkaTemplate\b', r'\b@KafkaListener\b',
            r'\bKafkaConsumer\b', r'\bProducerRecord\b',
        ],
        "idempotency_patterns": [
            r'\bidempotent\b', r'\b@DistributedLock\b',
            r'\bLock\b.*redis', r'\btryLock\b',
        ],
        "task_group_patterns": [
            r'\bAsyncTask\b', r'\b@Async\b',
            r'\bThreadPool\b', r'\bExecutor\b',
        ],
        "enum_pattern": r'\benum\s+\w+',
    },
}


# ── 通用检测函数 ────────────────────────────────────────────────

def detect_patterns(repo_paths: List[str], language: str = None) -> Dict:
    """检测项目中的架构模式.
    
    Args:
        repo_paths: 仓库路径列表
        language: 语言 ('go', 'python', 'java')，None 表示自动检测
    
    Returns:
        包含 7 类模式检测结果的字典
    """
    import time
    t0 = time.time()
    print(f"  🔍 Analyzing architectural patterns ({language or 'auto'})...")

    # 自动检测语言
    if not language:
        language = _detect_language(repo_paths)

    patterns = LANGUAGE_PATTERNS.get(language, LANGUAGE_PATTERNS["go"])
    paths = [Path(p) for p in repo_paths]

    results = {
        "language": language,
        "state_machines": _detect_state_machines(paths, patterns),
        "redis_locks": _detect_redis_patterns(paths, patterns),
        "retry_logic": _detect_retry_patterns(paths, patterns),
        "kafka_patterns": _detect_kafka_patterns(paths, patterns),
        "idempotency": _detect_idempotency_patterns(paths, patterns),
        "task_group_patterns": _detect_task_group_patterns(paths, patterns),
        "enums": _detect_enum_patterns(paths, language),
    }

    elapsed = time.time() - t0
    print(f"  Pattern analysis done in {elapsed:.1f}s")
    return results


def _detect_language(repo_paths: List[str]) -> str:
    """自动检测项目语言."""
    scores = {"go": 0, "python": 0, "java": 0}
    for repo in repo_paths:
        path = Path(repo)
        # 统计文件数量
        go_count = len(list(path.rglob("*.go")))
        py_count = len(list(path.rglob("*.py")))
        java_count = len(list(path.rglob("*.java")))
        scores["go"] += go_count
        scores["python"] += py_count
        scores["java"] += java_count
    return max(scores, key=scores.get) if max(scores.values()) > 0 else "go"


def _read_file_safe(f: Path) -> str:
    """安全读取文件内容."""
    try:
        return f.read_text(errors='ignore')
    except Exception:
        return ""


def _get_relative_path(f: Path, repo: Path) -> str:
    """获取相对路径."""
    try:
        return str(f.relative_to(repo))
    except ValueError:
        return str(f.name)


# ── 7 类模式检测 ────────────────────────────────────────────────

def _detect_state_machines(repo_paths: List[Path], patterns: Dict) -> List[Dict]:
    """检测状态机模式."""
    results = []
    seen = set()

    for repo in repo_paths:
        for f in repo.rglob("*"):
            if f.suffix not in ['.go', '.py', '.java']:
                continue
            if 'vendor/' in str(f) or '.git/' in str(f):
                continue
            text = _read_file_safe(f)
            if not text:
                continue

            rel_path = _get_relative_path(f, repo)
            lines = text.split('\n')

            # 查找状态相关函数
            for i, line in enumerate(lines):
                # 匹配函数定义
                func_match = None
                if f.suffix == '.go':
                    func_match = re.match(r'\s*func\s+(?:\([^)]+\)\s+)?(\w+)\s*\(', line)
                elif f.suffix == '.py':
                    func_match = re.match(r'\s*def\s+(\w+)', line)
                elif f.suffix == '.java':
                    func_match = re.match(r'\s*(?:public|private|protected)?\s*\w+\s+(\w+)\s*\(', line)

                if not func_match:
                    continue

                func_name = func_match.group(1)
                if func_name in seen:
                    continue

                # 检查函数体中是否有状态关键字
                body_start = i
                body_end = min(i + 50, len(lines))  # 检查函数体前50行
                body = '\n'.join(lines[body_start:body_end])

                if re.search(patterns["state_keywords"], body, re.I):
                    # 提取状态值
                    states = []
                    if f.suffix == '.go':
                        states = re.findall(r'(\w+(?:State|Status)\w*)\s*=\s*(\w+)', body)
                    elif f.suffix == '.py':
                        states = re.findall(r'(\w+(?:STATE|STATUS)\w*)\s*=\s*["\']?(\w+)["\']?', body)
                    elif f.suffix == '.java':
                        states = re.findall(r'(\w+(?:State|Status)\w*)\s*=\s*(\w+)', body)

                    if len(states) >= 2:
                        results.append({
                            'func': func_name,
                            'file': rel_path,
                            'line': i + 1,
                            'states': [f'{s[0]}={s[1]}' for s in states[:5]],
                            'pattern': '状态机',
                        })
                        seen.add(func_name)
                        break

    return results


def _detect_redis_patterns(repo_paths: List[Path], patterns: Dict) -> List[Dict]:
    """检测 Redis 分布式锁模式."""
    results = []
    seen = set()

    for repo in repo_paths:
        for f in repo.rglob("*"):
            if f.suffix not in ['.go', '.py', '.java']:
                continue
            if 'vendor/' in str(f) or '.git/' in str(f):
                continue
            text = _read_file_safe(f)
            if not text:
                continue

            rel_path = _get_relative_path(f, repo)

            for redis_pat in patterns["redis_patterns"]:
                matches = list(re.finditer(redis_pat, text, re.I))
                if not matches:
                    continue

                # 找到包含 Redis 调用的函数
                lines = text.split('\n')
                for match in matches[:3]:  # 每个文件最多3个
                    line_no = text[:match.start()].count('\n') + 1

                    # 向上查找函数定义
                    func_name = None
                    for i in range(line_no - 1, max(0, line_no - 30), -1):
                        line = lines[i]
                        if f.suffix == '.go' and re.match(r'\s*func\s+', line):
                            func_name = re.search(r'func\s+(\w+)', line)
                            break
                        elif f.suffix == '.py' and re.match(r'\s*def\s+', line):
                            func_name = re.search(r'def\s+(\w+)', line)
                            break
                        elif f.suffix == '.java' and re.match(r'\s*(?:public|private|protected)', line):
                            func_name = re.search(r'\w+\s+(\w+)\s*\(', line)
                            break
                        if line.strip().startswith('}') and f.suffix == '.go':
                            break

                    if func_name:
                        func_name = func_name.group(1)
                        key = f"{rel_path}:{func_name}"
                        if key in seen:
                            continue
                        seen.add(key)

                        results.append({
                            'func': func_name,
                            'file': rel_path,
                            'line': line_no,
                            'desc': f'Redis模式: {match.group(0)}',
                            'pattern': 'Redis锁',
                        })
                        break

    return results


def _detect_retry_patterns(repo_paths: List[Path], patterns: Dict) -> List[Dict]:
    """检测重试机制模式."""
    results = []
    seen = set()

    for repo in repo_paths:
        for f in repo.rglob("*"):
            if f.suffix not in ['.go', '.py', '.java']:
                continue
            if 'vendor/' in str(f) or '.git/' in str(f):
                continue
            text = _read_file_safe(f)
            if not text:
                continue

            rel_path = _get_relative_path(f, repo)

            for retry_pat in patterns["retry_patterns"]:
                if not re.search(retry_pat, text, re.I):
                    continue

                lines = text.split('\n')
                for i, line in enumerate(lines):
                    if re.search(retry_pat, line, re.I):
                        # 查找所在函数
                        func_name = None
                        for j in range(i, max(0, i - 20), -1):
                            l = lines[j]
                            if f.suffix == '.go' and re.match(r'\s*func\s+', l):
                                func_name = re.search(r'func\s+(\w+)', l)
                                break
                            elif f.suffix == '.py' and re.match(r'\s*def\s+', l):
                                func_name = re.search(r'def\s+(\w+)', l)
                                break
                            elif f.suffix == '.java' and re.match(r'\s*(?:public|private|protected)', l):
                                func_name = re.search(r'\w+\s+(\w+)\s*\(', l)
                                break
                            if l.strip() == '}' and f.suffix == '.go':
                                break

                        if func_name:
                            func_name = func_name.group(1)
                            key = f"{rel_path}:{func_name}"
                            if key in seen:
                                continue
                            seen.add(key)

                            results.append({
                                'func': func_name,
                                'file': rel_path,
                                'line': i + 1,
                                'desc': f'重试模式: {line.strip()[:60]}',
                                'pattern': '重试',
                            })
                            break
                if results and seen:
                    break

    return results


def _detect_kafka_patterns(repo_paths: List[Path], patterns: Dict) -> List[Dict]:
    """检测 Kafka/消息队列模式."""
    results = []
    seen = set()

    for repo in repo_paths:
        for f in repo.rglob("*"):
            if f.suffix not in ['.go', '.py', '.java']:
                continue
            if 'vendor/' in str(f) or '.git/' in str(f):
                continue
            text = _read_file_safe(f)
            if not text:
                continue

            rel_path = _get_relative_path(f, repo)

            for kafka_pat in patterns["kafka_patterns"]:
                if not re.search(kafka_pat, text, re.I):
                    continue

                # 找函数
                lines = text.split('\n')
                for i, line in enumerate(lines):
                    if re.search(kafka_pat, line, re.I):
                        func_name = None
                        for j in range(i, max(0, i - 30), -1):
                            l = lines[j]
                            if f.suffix == '.go' and re.match(r'\s*func\s+', l):
                                func_name = re.search(r'func\s+(\w+)', l)
                                break
                            elif f.suffix == '.py' and re.match(r'\s*def\s+', l):
                                func_name = re.search(r'def\s+(\w+)', l)
                                break
                            elif f.suffix == '.java' and re.match(r'\s*(?:public|private|protected)', l):
                                func_name = re.search(r'\w+\s+(\w+)\s*\(', l)
                                break
                            if l.strip().startswith('}') and f.suffix == '.go':
                                break

                        if func_name:
                            func_name = func_name.group(1)
                            key = f"{rel_path}:{func_name}"
                            if key not in seen:
                                seen.add(key)
                                results.append({
                                    'func': func_name,
                                    'file': rel_path,
                                    'line': i + 1,
                                    'desc': f'Kafka模式: {line.strip()[:60]}',
                                    'pattern': 'Kafka',
                                })
                if results:
                    break

    return results


def _detect_idempotency_patterns(repo_paths: List[Path], patterns: Dict) -> List[Dict]:
    """检测幂等性模式."""
    results = []
    seen = set()

    for repo in repo_paths:
        for f in repo.rglob("*"):
            if f.suffix not in ['.go', '.py', '.java']:
                continue
            if 'vendor/' in str(f) or '.git/' in str(f):
                continue
            text = _read_file_safe(f)
            if not text:
                continue

            rel_path = _get_relative_path(f, repo)

            for pat in patterns["idempotency_patterns"]:
                if not re.search(pat, text, re.I):
                    continue

                lines = text.split('\n')
                for i, line in enumerate(lines):
                    if re.search(pat, line, re.I):
                        func_name = None
                        for j in range(i, max(0, i - 30), -1):
                            l = lines[j]
                            if f.suffix == '.go' and re.match(r'\s*func\s+', l):
                                func_name = re.search(r'func\s+(\w+)', l)
                                break
                            elif f.suffix == '.py' and re.match(r'\s*def\s+', l):
                                func_name = re.search(r'def\s+(\w+)', l)
                                break
                            elif f.suffix == '.java' and re.match(r'\s*(?:public|private|protected)', l):
                                func_name = re.search(r'\w+\s+(\w+)\s*\(', l)
                                break

                        if func_name:
                            func_name = func_name.group(1)
                            key = f"{rel_path}:{func_name}"
                            if key not in seen:
                                seen.add(key)
                                results.append({
                                    'func': func_name,
                                    'file': rel_path,
                                    'line': i + 1,
                                    'desc': f'幂等模式: {line.strip()[:60]}',
                                    'pattern': '幂等',
                                })
                break

    return results


def _detect_task_group_patterns(repo_paths: List[Path], patterns: Dict) -> List[Dict]:
    """检测任务组模式."""
    results = []
    seen = set()

    for repo in repo_paths:
        for f in repo.rglob("*"):
            if f.suffix not in ['.go', '.py', '.java']:
                continue
            if 'vendor/' in str(f) or '.git/' in str(f):
                continue
            text = _read_file_safe(f)
            if not text:
                continue

            rel_path = _get_relative_path(f, repo)

            for pat in patterns["task_group_patterns"]:
                if not re.search(pat, text, re.I):
                    continue

                lines = text.split('\n')
                for i, line in enumerate(lines):
                    if re.search(pat, line, re.I):
                        func_name = None
                        for j in range(i, max(0, i - 30), -1):
                            l = lines[j]
                            if f.suffix == '.go' and re.match(r'\s*func\s+', l):
                                func_name = re.search(r'func\s+(\w+)', l)
                                break
                            elif f.suffix == '.py' and re.match(r'\s*def\s+', l):
                                func_name = re.search(r'def\s+(\w+)', l)
                                break
                            elif f.suffix == '.java' and re.match(r'\s*(?:public|private|protected)', l):
                                func_name = re.search(r'\w+\s+(\w+)\s*\(', l)
                                break

                        if func_name:
                            func_name = func_name.group(1)
                            key = f"{rel_path}:{func_name}"
                            if key not in seen:
                                seen.add(key)
                                results.append({
                                    'func': func_name,
                                    'file': rel_path,
                                    'line': i + 1,
                                    'desc': f'任务组模式: {line.strip()[:60]}',
                                    'pattern': '任务组',
                                })
                break

    return results


def _detect_enum_patterns(repo_paths: List[Path], language: str = "go") -> List[Dict]:
    """检测枚举/常量定义模式."""
    results = []
    seen_keys = set()

    for repo in repo_paths:
        count = 0
        for f in sorted(repo.rglob("*")):
            if f.suffix not in ['.go', '.py', '.java']:
                continue
            if 'vendor/' in str(f) or '.git/' in str(f) or '_test.go' in str(f):
                continue
            count += 1
            if count >= 500:
                break

            text = _read_file_safe(f)
            if not text:
                continue

            rel_path = _get_relative_path(f, repo)

            # Go const block
            if language == "go":
                const_blocks = re.findall(r'const\s*\((.*?)\)', text, re.DOTALL)
                for block in const_blocks:
                    entries = re.findall(r'^\s*(\w+)\s+[\w|*]+\s*=\s*([^/\n]+)', block, re.MULTILINE)
                    if len(entries) < 2:
                        entries = re.findall(r'^\s*(\w+)\s*=\s*([^/\n]+)', block, re.MULTILINE)
                    if len(entries) < 2:
                        continue

                    names = [e[0] for e in entries]
                    all_names = ' '.join(names)
                    if re.search(r'\b(type|Status|State|Action|Option|Type|Kind|Level)\b', all_names, re.I):
                        enum_type = '状态/类型枚举'
                    else:
                        enum_type = '常量组'

                    key = (rel_path, enum_type)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)

                    results.append({
                        'file': rel_path,
                        'line': 'const block',
                        'type': enum_type,
                        'count': len(entries),
                        'samples': [e[1].strip().split(',')[0].strip() for e in entries[:5]],
                        'names': names[:8],
                    })

            # Python Enum
            elif language == "python":
                enum_classes = re.findall(r'class\s+(\w+Enum|.*Enum)\s*\(', text)
                for cls in enum_classes:
                    key = (rel_path, cls)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    results.append({
                        'file': rel_path,
                        'line': 'class',
                        'type': 'Python Enum',
                        'count': 0,
                        'samples': [],
                        'names': [cls],
                    })

            # Java enum
            elif language == "java":
                enums = re.findall(r'\benum\s+(\w+)', text)
                for en in enums:
                    key = (rel_path, en)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    results.append({
                        'file': rel_path,
                        'line': 'enum',
                        'type': 'Java Enum',
                        'count': 0,
                        'samples': [],
                        'names': [en],
                    })

    return results


# ── 摘要生成 ────────────────────────────────────────────────────

def generate_pattern_summary(results: Dict) -> str:
    """生成模式检测摘要文本."""
    lines = []
    lines.append("## 架构模式检测\n")

    # 状态机
    sm = results.get('state_machines', [])
    if sm:
        lines.append(f"### 状态机 ({len(sm)} 个)\n")
        for item in sm[:5]:
            lines.append(f"- `{item['func']}` @ {item['file']}:{item['line']}")
            if 'states' in item:
                lines.append(f"  {', '.join(item['states'][:3])}")
        lines.append("")

    # Redis 锁
    redis = results.get('redis_locks', [])
    if redis:
        lines.append(f"### Redis 分布式锁 ({len(redis)} 个)\n")
        for item in redis[:5]:
            lines.append(f"- `{item['func']}` — {item['desc']}")
        lines.append("")

    # 重试
    retry = results.get('retry_logic', [])
    if retry:
        lines.append(f"### 重试机制 ({len(retry)} 个)\n")
        for item in retry[:5]:
            lines.append(f"- `{item['func']}` — {item['desc']}")
        lines.append("")

    # Kafka
    kafka = results.get('kafka_patterns', [])
    if kafka:
        lines.append(f"### Kafka/消息队列 ({len(kafka)} 个)\n")
        for item in kafka[:5]:
            lines.append(f"- `{item['func']}` — {item['desc']}")
        lines.append("")

    # 幂等
    idem = results.get('idempotency', [])
    if idem:
        lines.append(f"### 幂等性 ({len(idem)} 个)\n")
        for item in idem[:5]:
            lines.append(f"- `{item['func']}` — {item['desc']}")
        lines.append("")

    # 枚举
    enums = results.get('enums', [])
    if enums:
        lines.append(f"### 枚举/常量定义 ({len(enums)} 组)\n")
        for item in enums[:5]:
            lines.append(f"- `{item['file']}` ({item['type']}, {item['count']}个): {', '.join(item['names'][:4])}")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 universal_pattern_detector.py <repo_path> [repo_path2 ...]")
        sys.exit(1)

    results = detect_patterns(sys.argv[1:])
    print("\n" + generate_pattern_summary(results))
