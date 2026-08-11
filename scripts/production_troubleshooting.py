#!/usr/bin/env python3
"""
生产环境故障排查手册

记录常见生产问题和解决方案
"""

import re
from pathlib import Path
from typing import Dict, List, Tuple


class TroubleshootingGuide:
    """故障排查手册"""
    
    def __init__(self):
        self.cases = []
    
    def add_case(
        self,
        title: str,
        symptom: str,
        cause: str,
        solution: str,
        category: str = "general"
    ):
        """添加排查案例"""
        self.cases.append({
            "title": title,
            "symptom": symptom,
            "cause": cause,
            "solution": solution,
            "category": category,
        })
    
    def generate_report(self) -> str:
        """生成排查手册"""
        report = """# 生产环境故障排查手册

> 持续更新中...

## 一、数据库问题

### 1.1 MySQL 连接数满

**症状**:
- 应用报错：`Too many connections`
- 数据库连接池耗尽

**原因**:
- 慢查询占用连接
- 连接泄漏
- 连接池配置不当

**解决方案**:
```sql
-- 查看当前连接
SHOW PROCESSLIST;

-- 查看最大连接数
SHOW VARIABLES LIKE 'max_connections';

-- 调整配置
SET GLOBAL max_connections = 500;
```

```go
// Go 连接池配置
db.SetMaxOpenConns(100)
db.SetMaxIdleConns(10)
db.SetConnMaxLifetime(time.Hour)
```

---

### 1.2 慢查询导致性能下降

**症状**:
- 接口响应变慢
- 数据库 CPU 使用率高

**排查步骤**:
```sql
-- 开启慢查询日志
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 1;

-- 查看慢查询
SHOW VARIABLES LIKE 'slow_query_log%';
SHOW VARIABLES LIKE 'long_query_time';
```

**优化方案**:
```sql
-- 1. 添加索引
EXPLAIN SELECT * FROM orders WHERE user_id = 100;
ALTER TABLE orders ADD INDEX idx_user_id (user_id);

-- 2. 避免 SELECT *
SELECT id, user_id, status FROM orders;

-- 3. 使用覆盖索引
ALTER TABLE orders ADD INDEX idx_user_status (user_id, status);
```

---

### 1.3 死锁问题

**症状**:
- 报错：`Deadlock found when trying to get lock`
- 事务频繁回滚

**排查**:
```sql
-- 查看死锁信息
SHOW ENGINE INNODB STATUS;

-- 查看正在锁的事务
SELECT * FROM information_schema.innodb_locks;
```

**解决方案**:
```sql
-- 1. 统一访问顺序
-- 所有事务按相同顺序访问表

-- 2. 缩短事务
BEGIN;
-- 快速操作
UPDATE accounts SET balance = balance - 100 WHERE id = 1;
UPDATE accounts SET balance = balance + 100 WHERE id = 2;
COMMIT;

-- 3. 设置锁等待超时
SET innodb_lock_wait_timeout = 50;
```

---

## 二、缓存问题

### 2.1 缓存穿透

**症状**:
- Redis 大量空值查询
- 数据库压力突增

**解决方案**:
```go
// 布隆过滤器
bloom := bloom.NewWithEstimates(1000000, 0.01)
bloom.Add([]byte(key))

// 缓存空值
redis.Set(key, "", 30*time.Second)
```

### 2.2 缓存击穿

**症状**:
- 热点 key 过期，大量请求打到 DB

**解决方案**:
```go
// 互斥锁
mu := sync.Mutex{}
mu.Lock()
defer mu.Unlock()

// 双重检查
val := redis.Get(key)
if val == "" {
    val = db.Get(key)
    redis.Set(key, val, time.Hour)
}
```

### 2.3 缓存雪崩

**症状**:
- 大量 key 同时过期

**解决方案**:
```go
// TTL 加随机值
ttl := baseTTL + time.Duration(rand.Intn(int(baseTTL/4)))
redis.Set(key, value, ttl)
```

---

## 三、并发问题

### 3.1 Goroutine 泄漏

**症状**:
- 内存持续增长
- 系统变慢

**排查**:
```go
// 查看 goroutine 数量
import "runtime"
println(runtime.NumGoroutine())

// pprof 分析
import _ "net/http/pprof"
http.ListenAndServe("localhost:6060", nil)
```

**常见原因**:
```go
// ❌ 错误：channel 未接收
ch := make(chan int)
go func() { ch <- 1 }()

// ✅ 正确：确保 channel 有接收方
go func() { <-ch }()
```

### 3.2 死锁

**症状**:
- 程序卡住，无响应

**排查**:
```go
// 设置死锁检测
runtime.SetMutexProfileFraction(1)

// 分析
go tool pprof http://localhost:6060/debug/pprof/mutex
```

---

## 四、网络问题

### 4.1 连接超时

**症状**:
- 请求超时
- 连接被拒绝

**排查**:
```bash
# 查看网络连接
netstat -an | grep 8080

# 查看端口占用
lsof -i :8080

# 测试连接
telnet host port
curl -v http://host:port
```

**解决方案**:
```go
// 配置超时
client := &http.Client{
    Timeout: 5 * time.Second,
    Transport: &http.Transport{
        DialTimeout: 3 * time.Second,
        TLSHandshakeTimeout: 3 * time.Second,
    },
}
```

### 4.2 文件描述符耗尽

**症状**:
- 报错：`too many open files`

**排查**:
```bash
# 查看当前限制
ulimit -n

# 查看进程打开文件数
lsof -p <pid> | wc -l
```

**解决方案**:
```bash
# 调整限制
ulimit -n 65535

# 永久修改
echo "* soft nofile 65535" >> /etc/security/limits.conf
echo "* hard nofile 65535" >> /etc/security/limits.conf
```

---

## 五、内存问题

### 5.1 内存泄漏

**症状**:
- 内存持续增长
- OOM 崩溃

**排查**:
```go
// pprof heap
go tool pprof http://localhost:6060/debug/pprof/heap

// 查看分配
go tool pprof -alloc_space http://localhost:6060/debug/pprof/heap
```

**常见原因**:
```go
// ❌ 全局 map 无限增长
var cache = make(map[string]interface{})

// ✅ 使用带过期时间的缓存
type Cache struct {
    data map[string]*Item
    mu   sync.Mutex
}
```

---

## 六、排查工具

### 6.1 Linux 工具

```bash
# CPU 使用率
top -p <pid>

# 内存使用
free -h
ps aux | grep <process>

# 磁盘 IO
iostat -x 1

# 网络
netstat -an
ss -tn

# 系统调用
strace -p <pid>

# 性能分析
perf top
```

### 6.2 Go 工具

```bash
# CPU Profiling
go tool pprof http://localhost:6060/debug/pprof/profile

# Memory Profiling
go tool pprof http://localhost:6060/debug/pprof/heap

# Goroutine Profiling
go tool pprof http://localhost:6060/debug/pprof/goroutine

# Block Profiling
go tool pprof http://localhost:6060/debug/pprof/block
```

---

## 七、应急预案

### 7.1 快速止损

```bash
# 1. 重启服务
systemctl restart app

# 2. 回滚版本
git checkout v1.0.0
make deploy

# 3. 降级功能
feature_flag.disable("new_feature")

# 4. 限流
rate_limiter.set_limit(1000)
```

### 7.2 事故复盘

```markdown
## 事故报告

- 时间：
- 影响：
- 原因：
- 解决：
- 改进：
```

---

## 八、预防措施

1. **监控告警**
   - CPU、内存、磁盘监控
   - QPS、延迟、错误率监控
   - 关键业务指标监控

2. **容量规划**
   - 定期压测
   - 预留 30% 余量
   - 弹性伸缩

3. **故障演练**
   - 混沌工程
   - 应急预案演练
   - 定期复盘

---

*最后更新：2026-08-11*
*作者：Ryan*
"""
        return report


def main():
    """主入口"""
    guide = TroubleshootingGuide()
    
    # 添加案例
    guide.add_case(
        "MySQL连接数满",
        "Too many connections",
        "慢查询/连接泄漏",
        "调整连接池配置",
        "database"
    )
    
    guide.add_case(
        "缓存穿透",
        "大量空值查询",
        "查询不存在的数据",
        "布隆过滤器/缓存空值",
        "cache"
    )
    
    guide.add_case(
        "Goroutine泄漏",
        "内存持续增长",
        "channel未接收",
        "pprof分析",
        "concurrency"
    )
    
    # 生成报告
    report = guide.generate_report()
    
    output_path = Path("/tmp/troubleshooting_guide.md")
    output_path.write_text(report, encoding="utf-8")
    print(f"📄 排查手册已保存: {output_path}")
    
    # 打印摘要
    print("\n" + "=" * 60)
    print("    故障排查手册摘要")
    print("=" * 60)
    print(report[:3000])


if __name__ == "__main__":
    main()
