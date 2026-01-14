# Developer Notes & AI Context

此文档记录项目的演进历史、设计决策及 AI 协作上下文，旨在帮助后续的 AI 助手快速理解项目状态。

## 项目定位
**Docker IPv6 Firewall Manager** 是一个专为 `macvlan` 和 `ipvlan` 等复杂 Docker 网络设计的防火墙控制器。它解决了 Docker 在这些网络模式下无法自动管理 IPv6 iptables 规则的痛点。

## 关键技术点
- **IPv6 NAT**: 不仅支持简单的 Forward，还支持 NAT (DNAT/SNAT) 以实现端口重映射。
- **System Integration**: 深度集成 Systemd，非单纯的脚本，而是守护进程。
- **Dynamic Monitoring**: 通过 Docker Events API 实时响应。

## 版本演进记录

### v1.4.2 (Current Work)
- **Fix**: 解决了 Service 容器触发重复规则的问题（Double Rule Bug）。
- **UX**: 优化了 iptables 注释位置，便于 `iptables -S` 查看。
- **Docs**: 重构文档结构。

### v1.4.1 (2026-01-15)
- **Feature**: Swarm Worker Node 支持（Graceful Degradation）。
- **Feature**: Exclusive Mode（独占模式），标签定义优于原生端口。
- **Fix**: 修复了 FORWARD 链使用外部端口而非内部端口的严重 BUG。

### v1.3.x
- **Feature**: 基础的 macvlan 支持。
- **Feature**: Systemd 集成。

## 已知问题与待办
1. **Rule Duplication**: 在 v1.4.1 中，如果容器同时拥有 Service Name 标签和 Custom Ports 标签，会重复添加规则。已在 v1.4.2 修复。
2. **Comment Order**: `ip6tables` 命令对注释参数的位置敏感，可能导致输出不如预期美观。正在调整参数顺序。

## AI 协作建议
- **修改逻辑时**: 请务必检查 `docker_monitor.py` 中的 `_process_container` 方法，这是规则生成的入口。
- **测试**: 任何涉及 iptables 规则生成的修改，都必须通过 `test/test_docker_monitor_std.py` 进行验证。
- **部署**: 使用 `./build.sh` 构建 deb 包是唯一的官方部署方式。
