# Contributing

感谢你改进 `mcp-policy-forge`。这个项目的核心目标是让 MCP 权限策略可读、可审计、可测试、可接 CI。

## 本地开发

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

## 代码约定

- 优先使用 Python 标准库。
- 保持 Python 3.9+ 兼容。
- 新增策略语义时同时补测试。
- 不提交真实 token、个人信息、内部域名或私有 transcript。
- CLI 行为变更需要更新 README。

## 测试重点

- manifest 和 transcript 解析。
- action/path/network 推断。
- allow/deny 规则匹配。
- path escape 检查。
- 风险评分边界。
- JSON、Markdown、JUnit 输出。
- CLI 退出码。

