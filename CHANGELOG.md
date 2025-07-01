# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- IPv4 规则支持
- 更多网络驱动支持
- 规则模板配置
- Web 管理界面
- 性能监控和统计

## [1.3.4] - 2025-07-01

### Added
- **完整的Docker Swarm Service支持** - 全面支持Service端口发布和NAT转换
- **Service容器动态检测** - 容器启动时自动检测是否属于Service并触发处理
- **Service删除事件监听** - 监听Docker Service删除事件，自动清理规则
- **周期性扫描兜底机制** - 每1分钟自动扫描容器和Service状态，确保规则一致性
- **陈旧规则清理机制** - 周期性检查并清理已不存在的容器和Service规则
- **Docker重连机制** - 事件监控断开时自动重新连接Docker

### Fixed
- **严重修复**: Service规则添加失败的Bug（重复方法定义问题）
- **严重修复**: Service停止时规则不被删除的问题
- **规则冲突问题** - 新Service使用相同IP/端口时被旧规则阻挡的问题
- **启动时序问题** - 系统重启后Service识别不到的问题
- **事件监控断开** - Docker服务重启后事件监控断开的问题
- Service规则泄漏导致的网络访问异常

### Enhanced
- **智能Service检测** - 通过容器标签自动识别Service容器
- **完整的事件监听** - 同时监听container和service类型事件
- **双重保障机制** - 事件驱动 + 周期性扫描，确保状态始终一致
- **规则一致性保障** - 确保内存规则与实际Docker状态一致
- **容错能力提升** - Docker服务异常时自动重连和状态恢复
- **规则泄漏防护** - 防止相同IP/端口的新Service被旧规则干扰

### Technical
- 修复重复的 `add_service_rules` 方法定义
- 新增 `_check_and_handle_service_container()` 方法
- 新增Service事件监听：`event.get('Type') == 'service'`
- 新增 `_handle_service_remove()` 方法处理Service删除
- 新增 `_cleanup_stale_rules()` 方法清理陈旧规则
- 新增 `_periodic_scan()` 周期性扫描方法（1分钟间隔）
- 改进事件监控异常处理，增加Docker重连逻辑
- 通过 `com.docker.swarm.service.name` 标签识别Service容器
- 周期性扫描集成规则清理检查

## [1.3.3] - 2025-07-01

### Added
- **ICMPv6/NDP协议FORWARD支持** - 添加主接口与macvlan网关间的ICMPv6双向转发规则
- 确保IPv6邻居发现协议(NDP)在接口间正常工作
- 支持路径MTU发现和ICMPv6错误报告的转发

### Enhanced
- **网络基础设施完善** - 保证IPv6网络协议栈的完整性
- **接口间协议转发** - `parent_interface ↔ gateway_macvlan` ICMPv6双向转发

### Technical
- 新增 `_setup_icmpv6_forward_rules()` 方法
- ICMPv6 FORWARD规则自动添加到专用链中
- 最小化改动，只添加必要的协议转发规则

## [1.3.2] - 2025-07-01

### Added
- **完整的专用链架构** - 所有规则现在都在专用链中，便于管理和清理
- **三层专用链设计**：
  - `DOCKER_IPV6FW_FORWARD` - 容器和Service FORWARD规则
  - `DOCKER_IPV6FW_INPUT` - IPv6基础协议规则
  - `DOCKER_IPV6FW_NAT` - Service NAT规则

### Enhanced
- **链引用检查机制** - 确保专用链正确引用到系统链
- **统一的链管理** - 所有专用链的创建、清理和状态检查
- **更清晰的链命名** - 添加 `FW` 前缀，明确标识防火墙相关链

### Fixed
- **重要修复**: FORWARD链引用丢失问题
- 自定义链存在但未被FORWARD链引用的问题
- 链创建逻辑改进，同时检查链存在性和引用状态

### Technical
- 新增 `_ensure_all_chains_exist()` 方法管理所有专用链
- 新增 `_ensure_input_chain_exists()` 和 `_ensure_nat_chain_exists()` 方法
- 改进的 `_ensure_chain_exists()` 方法，检查链引用状态
- IPv6基础规则和NAT规则现在使用专用链
- 完全消除硬编码：系统命令、IPv6地址范围等都可配置

### Benefits
- **易于清理** - 三条命令即可清空所有规则
- **易于识别** - 所有规则都有明确的链标识
- **故障恢复** - 程序崩溃后人工清理简单
- **规则隔离** - 不会与系统原有规则混合

## [1.3.1] - 2025-07-01

### Fixed
- 协议硬编码问题 - 移除tcp/udp硬编码，支持所有协议
- IPv6地址硬编码问题 - 动态获取容器地址
- 端口号硬编码问题 - 动态获取端口配置
- 状态同步逻辑错误 - 正确区分容器规则和Service规则
- 防火墙规则解析错误 - 修正ip6tables输出字段解析

### Technical
- 改进的状态同步逻辑，支持动态规则识别
- 消除所有协议、地址、端口相关的硬编码

## [1.3.0] - 2025-06-30

### Added
- **Docker Swarm Service支持** - 自动管理Swarm Service的端口发布规则
- **Service端口NAT转换** - 支持PublishedPort到TargetPort的自动转换（如802->80）
- **本节点Service识别** - 只管理运行在本节点的Service容器
- **动态协议支持** - 自动从Service配置获取协议类型（tcp/udp等）
- **版本管理系统** - 统一的版本号管理，消除硬编码
- **版本管理脚本** - 支持版本号查看、设置和自动递增

### Enhanced
- **安全删除机制** - 只删除我们添加的规则，保护系统原有规则
- **代码质量改进** - 消除代码重复，统一规则构建逻辑
- **防重复删除保护** - 删除前检查规则是否存在，避免操作异常
- **代码复用改进** - prerm和管理脚本调用项目代码而非硬编码

### Fixed
- **重要修复**: 移除了错误的宽泛防火墙规则
- 防火墙规则逻辑错误 - 之前的基础转发规则允许所有流量通过
- IPv6地址格式错误 - NAT规则中的IPv6地址格式修复
- 版本号硬编码问题 - 实现统一版本管理

### Technical
- 新增Service规则管理：`_build_service_forward_rule()`, `_build_service_nat_rule()`
- 增强的清理机制，包含IPv6基础规则和Service规则清理
- 统一的规则构建逻辑，避免代码重复
- 版本管理统一化：VERSION文件 + 管理脚本 + Makefile集成

## [1.2.0] - 2025-06-30

### Added
- **IPv6基础协议支持** - 自动添加ICMPv6和NDP协议规则
- IPv6网络正常工作所需的基础规则（destination-unreachable, packet-too-big等）
- 邻居发现协议(NDP)支持（neighbor-solicitation, neighbor-advertisement等）
- 链路本地地址(fe80::/10)支持

### Enhanced
- 防火墙规则清理机制现在包含IPv6基础规则
- 卸载时自动清理所有相关规则
- 更精确的防火墙规则，只允许必要的流量

### Technical
- 新增IPv6基础协议规则管理
- 增强的清理机制，包含IPv6基础规则清理

## [1.1.0] - 2025-06-30

### Added
- **配置热重载功能** - 支持运行时重新加载配置文件
- **配置验证系统** - 完整的配置文件验证和错误提示
- **配置管理工具** - 独立的配置验证和修复工具
- **无效配置保护** - 服务在无效配置下不会崩溃，继续使用旧配置运行

### Enhanced
- 配置文件自动监控和变化检测
- SIGHUP信号支持配置重载
- 详细的配置验证错误信息
- 自动配置修复功能
- 管理工具新增配置相关命令

### Technical
- 新增 `scripts/validate-config.py` 配置验证工具
- 新增配置文件监控线程
- 增强的配置类，支持验证和热重载
- SIGHUP信号处理器
- 配置错误的优雅处理机制

### Commands
- `./scripts/manage.sh config` - 验证配置文件
- `./scripts/manage.sh reload` - 热重载配置
- `python3 scripts/validate-config.py` - 独立配置验证
- `systemctl reload docker-ipv6-firewall` - 系统级配置重载

## [1.0.1] - 2025-06-30

### Fixed
- **重要修复**: 服务启动和停止时的防火墙规则清理逻辑
- 服务异常退出时防火墙规则残留问题
- 服务重启后规则与实际容器状态不一致问题

### Added
- 服务启动时强制清空旧规则机制
- 服务停止时完整的规则清理机制
- 防火墙规则状态同步检查功能
- 管理工具 `scripts/manage.sh` 用于状态检查和维护
- 强制清理功能，支持基于规则特征的清理
- 规则一致性检查和报告

### Enhanced
- 改进的错误处理和异常保护
- 更详细的日志记录和状态报告
- 卸载时自动清理防火墙规则
- 配置文件优化，移除冗余配置项

### Technical
- 新增 `_flush_chain()` 方法用于清空防火墙链
- 新增 `sync_rules_with_reality()` 方法用于状态同步
- 新增 `force_cleanup_all_container_rules()` 方法用于强制清理
- 改进的服务生命周期管理

## [1.0.0] - 2025-06-30

### Added
- 初始版本发布
- 自动监控 Docker 容器启动/停止事件
- 动态管理 IPv6 防火墙规则（ip6tables）
- 支持 macvlan 和 bridge 网络类型
- 防火墙规则重复检查机制
- systemd 服务集成
- Debian 包构建和安装
- 完整的配置文件管理
- 详细的日志记录

### Features
- **Docker 事件监控**：实时监听容器生命周期事件
- **智能规则管理**：基于容器端口暴露自动生成防火墙规则
- **网络类型支持**：支持 macvlan 和 bridge 网络
- **配置化管理**：通过 YAML 配置文件灵活配置
- **系统服务**：完整的 systemd 集成，开机自启动
- **安全特性**：规则重复检查，自动清理，详细审计日志

### Technical Details
- **语言**：Python 3.9+
- **依赖**：python3-docker, python3-yaml, iptables, systemd
- **架构**：模块化设计，事件驱动
- **性能**：低内存占用（~30-50MB），事件驱动无 CPU 浪费

