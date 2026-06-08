# Security Policy

`mcp-policy-forge` 是本地策略生成与校验工具，不会主动联网，也不会执行 MCP server。

## Reporting

如果你发现安全问题，请在发布仓库后使用项目维护者提供的私有渠道报告。不要在公开 issue 中包含真实 token、私有 transcript、内部 host 或敏感路径。

## Handling Sensitive Data

- 不要把真实 token、password、API key 放入 manifest、transcript、policy 或测试 fixture。
- transcript 应该脱敏，只保留工具名、参数结构和必要路径/域名。
- 输出报告可能包含路径和域名，应按组织安全规范保存。

## Threat Model

本项目关注 MCP 工具权限建模和静态/半静态审计。它不能替代：

- MCP host 的真实沙箱。
- 操作系统权限控制。
- 网络 egress 防火墙。
- 人工安全评审。

