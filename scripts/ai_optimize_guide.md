# AI 优化指南

当 Pi 检测到触发文件后，AI 应该执行以下步骤：

## 1. 分析项目结构
```bash
ls -la
find . -name "*.py" -o -name "*.go" | head -50
ls skills/
ls templates/
```

## 2. 识别薄弱领域
- 运行测试：`python3 -m pytest tests/ -v`
- 检查覆盖率：`python3 -m pytest tests/ --cov=scripts --cov-report=term-missing`
- 查找 TODO/FIXME 注释
- 分析代码复杂度

## 3. 生成高质量文档
每个优化应该包含：
- **技术实现**：完整的代码示例
- **架构图**：使用 PlantUML 或 Mermaid
- **代码密度**：≥25%（代码行数/总行数）
- **字数**：≥2000 字

## 4. Git 提交
```bash
git add -A
git commit -m "feat: <优化描述>"
git push origin main
```

## 5. 显示结果
在对话中输出：
- 优化内容摘要
- 新增/修改的文件列表
- 测试结果
- 覆盖率变化

## 示例优化任务

### PRD Review 规则优化
1. 分析现有规则
2. 识别缺失的检查项
3. 添加新规则（如：验收标准、回滚方案）
4. 更新测试用例
5. 验证规则有效性

### Skill 模板完善
1. 检查现有模板
2. 识别缺失的语言支持
3. 添加新模板（如：Java, TypeScript）
4. 更新文档
5. 运行测试验证

### 测试用例补充
1. 分析现有测试覆盖
2. 识别边界条件
3. 添加测试用例
4. 运行测试验证
5. 检查覆盖率提升
