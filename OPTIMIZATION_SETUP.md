# biz-delivery 定时优化配置说明

> 配置日期：2026-08-12  
> 状态：✅ 已启用

---

## 🚀 配置状态

| 组件 | 状态 | 说明 |
|------|------|------|
| **本地 Cron** | ✅ 已设置 | 每小时自动运行 |
| **GitHub Actions** | ⏳ 待推送 | 推送代码后自动启用 |
| **自动优化脚本** | ✅ 已创建 | `scripts/auto_optimize.py` |
| **优化清单** | ✅ 已创建 | `OPTIMIZATION_CHECKLIST.md` |

---

## 📋 定时任务详情

```cron
# 每小时运行一次自动化优化
0 * * * * cd /Users/yanping.ma/biz-delivery && python3 scripts/auto_optimize.py >> /tmp/biz-delivery-optimize.log 2>&1
```

---

## 🔧 管理命令

### 查看当前 cron 任务
```bash
crontab -l | grep biz-delivery
```

### 查看优化日志
```bash
tail -f /tmp/biz-delivery-optimize.log
```

### 手动运行优化
```bash
cd /Users/yanping.ma/biz-delivery && python3 scripts/auto_optimize.py
```

### 取消定时任务
```bash
crontab -e
# 删除包含 biz-delivery 的那一行
```

### 重新设置（如果需要）
```bash
bash setup_cron.sh
```

---

## 📊 优化流程

每次运行会自动执行：

1. **代码质量检查** - Python 语法检查
2. **测试运行** - pytest 测试套件
3. **Skill 覆盖分析** - 统计 Skill 数量和测试覆盖率
4. **生成优化报告** - 更新 OPTIMIZATION_LOG.md

---

## 🎯 下次运行时间

```
下一个整点（如现在是 14:23，将在 15:00 运行）
```

---

## 💡 提示

- 日志文件位于：`/tmp/biz-delivery-optimize.log`
- 优化报告位于：`OPTIMIZATION_LOG.md`
- 如需更频繁的运行，可修改 cron 表达式：
  - 每 30 分钟：`*/30 * * * *`
  - 每 15 分钟：`*/15 * * * *`

---

*配置完成于 2026-08-12*
