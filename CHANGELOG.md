## [1.4.2] - 2026-01-15

### Fixed
- **Duplicate Rules**: 修复了 Swarm Service 容器同时触发 Service 规则和自定义规则导致重复添加的问题。现在检测到 Service 上下文时会自动跳过自定义规则处理。
- **Comment Position**: 调整了 `iptables` 命令参数顺序，将 `--comment` 移至链表操作的末尾，以改善查看输出时的可读性。

### Documentation
- 重构了文档结构，将高级特性移至 `docs/FEATURES.md`。
- 新增 `docs/DEV_NOTES.md` 记录开发上下文。



### Added
- **Swarm Worker Node Support**: 实现了优雅降级机制，支持在无 Manager 权限的节点上运行。当 `docker service inspect` 失败时，自动切换到基于本地容器 Labels 的信息推导模式。
- **Exclusive Mode (独占模式)**: 新增冲突解决策略。当检测到 `docker-ipv6-firewall.ports` 标签时，自动忽略容器所有原生的端口映射，仅使用标签定义的规则。这提供了更精确的端口暴露控制。
- **Rule Comments**: 为生成的 `ip6tables` 规则添加了 `--comment`，清晰标识每条规则所属的 Service 或容器名称及端口映射关系。

### Fixed
- **Forward Chain Port Logic**: 修复了 Service 规则中 FORWARD 链使用外部端口导致数据包被丢弃的严重 Bug。现在正确使用 DNAT 后的目标端口 (Internal Port)。
- **Startup Sync**: 优化了规则同步逻辑，解决了重启服务时偶发的规则重复问题。



### Planned
- 更多网络驱动支持
- 规则模板配置
- Web 管理界面
- 性能监控和统计

## [1.3.8] - 2025-07-01

### Added
- **自定义防火墙端口配置** - 通过Docker Labels配置端口映射，不占用主机端口
- **灵活的端口映射语法** - 支持简单端口、端口映射、多端口配置
- **多协议支持** - 支持tcp/udp/all三种协议，all协议自动展开为tcp+udp
- **完整的使用文档** - 提供详细的配置示例和API文档

### Fixed
- **重大修复**: 端口分类逻辑错误 - 正确区分Public端口和自定义端口，避免重复规则
- **重大修复**: Service规则识别错误 - 修复"Service规则不一致"警告，正确识别Service容器IPv6地址
- **重大修复**: IPv4规则残留问题 - 服务停止时正确清理IPv4防火墙规则
- **重大安全修复**: 容器隔离漏洞 - 添加INPUT链规则阻止容器访问主机本地服务，保留ICMP/ICMPv6协议
- **重大修复**: DNAT端口访问问题 - 添加conntrack规则支持NAT映射端口访问
- **重大修复**: 安全规则优先级 - 容器隔离规则插入到INPUT链第一位，确保最高优先级
- **性能优化**: 相同端口映射不再创建多余的NAT规则 - 充分利用IPv6直接访问能力
- **网络模式处理不完整** - 支持Host、Bridge、Overlay等不同网络模式的端口获取
- **协议硬编码问题** - 修复所有方法中的协议硬编码，正确支持tcp/udp/all协议
- **Service自定义端口支持** - 支持从Service配置中读取自定义防火墙端口，解决Docker Swarm Labels传递问题

### Removed
- **废弃EXPOSE端口处理** - 完全移除容器EXPOSE端口的自动处理逻辑
- **简化端口分类** - 不再区分EXPOSE端口和其他端口类型
- **移除镜像端口处理** - 不再自动处理Dockerfile中的EXPOSE指令

### Enhanced
- **简化端口分类系统** - 只处理Service端口、Public端口和自定义端口三种类型
- **多网络模式支持** - 完整支持Host、Bridge、Overlay网络模式的端口处理
- **IPv6网络优化** - 相同端口映射直接通过FORWARD规则处理，无需NAT转换
- **处理流程简化** - 移除复杂的EXPOSE端口处理逻辑，提高性能

### Technical
- 新增 `_extract_custom_firewall_ports()` 方法解析自定义端口配置
- 新增 `add_custom_firewall_rules()` 方法处理自定义防火墙规则
- 重构 `_extract_container_ports()` 方法替代 `_extract_port_mappings()`
- 新增 `add_container_public_rules()` 方法处理容器Public端口
- 优化端口处理流程，支持多种网络模式和端口类型
- 新增 `_ensure_container_isolation_rules()` 方法实现容器安全隔离
- 新增 `_get_service_custom_ports()` 方法支持Service自定义端口

### Security
- **容器隔离增强**:
  - IPv4: `iptables -I INPUT 1 -i macvlan_gw ! -p icmp -m addrtype --dst-type LOCAL -j DROP`
  - IPv6: `ip6tables -I INPUT 1 -i macvlan_gw ! -p ipv6-icmp -m addrtype --dst-type LOCAL -j DROP`
- **保留必要协议**: 允许ICMP/ICMPv6用于网络诊断和NDP
- **精确目标控制**: 使用`--dst-type LOCAL`只保护主机本地地址
- **最高优先级**: 安全规则插入到第一位，不会被其他规则绕过
- **DNAT连接跟踪**: 使用conntrack状态跟踪优化NAT后端口访问

### Configuration Syntax
```yaml
labels:
  - "docker-ipv6-firewall.ports=80,443/tcp,53/udp,8080:80/tcp,9000/all"
```

### Benefits
- **解决主机端口占用问题** - 不再需要使用ports映射占用主机端口
- **简化端口管理** - 只处理明确配置的端口，不再自动处理EXPOSE端口
- **完整的网络支持** - 支持Docker的所有主要网络模式
- **更好的IPv6支持** - 充分利用IPv6的直接访问能力
- **提高性能** - 移除EXPOSE端口处理逻辑，减少不必要的规则检查

### Examples
```yaml
# 传统方式（占用主机端口）
ports: ["[::]:809:80"]

# 自定义方式（不占用主机端口）
labels:
  - "docker-ipv6-firewall.ports=809:80/tcp"
```

### Fixed
- **重大修复**: 端口分类逻辑错误 - 正确区分EXPOSE端口和Public端口，避免重复规则
- **重大修复**: 网络模式处理不完整 - 支持Host、Bridge、Overlay等不同网络模式的端口获取
- **重大修复**: Public端口规则创建错误 - Public端口现在正确创建NAT+FORWARD规则，EXPOSE端口只创建FORWARD规则
- 容器端口处理逻辑重构 - 智能识别端口类型和网络模式

### Added
- **智能端口分类系统** - 自动区分EXPOSE端口、Public端口和Service端口
- **多网络模式支持** - 完整支持Host、Bridge、Overlay网络模式的端口处理
- **端口来源检测** - 支持PortBindings、NetworkSettings.Ports、Service.EndpointSpec.Ports等多种端口来源
- **Service容器识别** - 通过Labels自动识别Service容器并特殊处理

### Enhanced
- **端口重叠处理** - Public端口优先级高于EXPOSE端口，避免同一端口创建重复规则
- **网络模式检测** - 根据NetworkMode自动调整端口处理策略
- **详细调试日志** - 增加端口提取过程的详细日志，便于故障排除
- **规则创建优化** - 不同类型端口创建对应类型的防火墙规则

### Technical
- 新增 `_extract_container_ports()` 方法替代 `_extract_port_mappings()`
- 新增 `add_container_public_rules()` 方法处理容器Public端口
- 新增 `_container_public_rules_changed()` 方法检测Public端口变化
- 重构端口处理流程，支持多种网络模式和端口类型
- 优化端口信息提取逻辑，提高准确性和可靠性

### Benefits
- **正确的端口规则** - 解决端口规则混乱和重复的问题
- **完整的网络支持** - 支持Docker的所有主要网络模式
- **精确的端口分类** - 每种端口类型都有对应的正确规则
- **更好的性能** - 避免重复规则，提高防火墙效率

### Root Cause Analysis
- **问题根因**: 原有代码将所有EXPOSE端口都当作需要FORWARD规则的端口处理，没有区分Public端口和纯EXPOSE端口
- **修复方案**: 重新设计端口分类逻辑，根据端口来源和网络模式创建对应类型的规则
- **验证结果**: 容器a10e6a2aa1f8现在正确创建1个EXPOSE规则(443)和3个Public规则(444→443, 80→80, 81→60081)

## [1.3.6] - 2025-07-01

### Fixed
- **严重修复**: Service端口映射变化时规则不更新的问题 - 修复add_service_rules中的逻辑缺陷
- **严重修复**: 周期性扫描无法检测Service配置变化的问题 - Service端口从805改为806时规则未更新
- Service规则变化检测逻辑错误 - 现在会正确比较端口、协议、容器IPv6地址等变化

### Added
- **Service规则变化检测机制** - 实现详细的规则比较逻辑，检测端口、协议、容器等变化
- **智能Service规则更新** - 检测到变化时先移除旧规则，再添加新规则
- **增强的调试日志** - 详细记录Service规则变化检测过程和端口映射信息

### Enhanced
- **周期性扫描改进** - 现在能够正确检测和处理Service配置变化
- **Service更新日志** - 增加详细的Service检查和规则更新日志
- **规则一致性保障** - 确保防火墙规则与实际Service配置始终保持一致

### Technical
- 修复 `add_service_rules()` 方法中的早期返回逻辑缺陷
- 新增 `_service_rules_changed()` 方法实现规则变化检测
- 改进周期性扫描的日志级别和详细程度
- 增强Service规则的调试信息输出

### Benefits
- **Service端口变化正确处理** - 解决Service端口映射变化时访问失败的问题
- **实时配置同步** - 周期性扫描能够检测并修复配置不一致
- **更好的故障排除** - 详细的日志便于诊断Service规则问题
- **系统稳定性提升** - 防止Service配置变化导致的网络访问异常

## [1.3.5] - 2025-07-01

### Added
- **完整的IPv4防火墙支持** - 为IPv4创建专用链架构，确保规则组织性和安全清理
- **IPv4专用链设计** - `DOCKER_IPV4FW_FORWARD`（FORWARD规则）和`DOCKER_IPV4FW_NAT`（NAT规则）
- **IPv4容器上网完整规则** - 添加容器到外网的FORWARD规则和NAT MASQUERADE规则
- **IPv4规则安全管理** - 所有IPv4规则现在都在专用链中，避免与系统规则混合

### Fixed
- **重要修复**: IPv4容器无法上网的问题 - 添加缺失的FORWARD和NAT规则
- **重要修复**: IPv4规则重复添加和误删系统规则的问题 - 使用专用链管理
- IPv4 ICMP转发规则现在使用专用链而非直接添加到系统FORWARD链

### Enhanced
- **统一的链管理架构** - IPv4和IPv6都使用相同的专用链管理模式
- **完整的IPv4网络支持** - 支持容器访问外网的所有必要规则
- **规则清理安全性** - IPv4规则清理不会影响系统原有规则

### Technical
- 新增 `ipv4_chain_name` 和 `ipv4_nat_chain_name` 配置项
- 新增 `_ensure_ipv4_nat_chain_exists()` 方法管理IPv4 NAT链
- 新增 `_setup_ipv4_container_internet_rules()` 方法设置IPv4上网规则
- 扩展 `_ensure_all_chains_exist()` 和 `_flush_all_chains()` 支持IPv4
- IPv4 ICMP规则迁移到专用链：`DOCKER_IPV4FW_FORWARD`
- IPv4 NAT规则使用专用链：`DOCKER_IPV4FW_NAT`

### Benefits
- **IPv4容器正常上网** - 解决容器无法访问外网的问题
- **规则管理一致性** - IPv4和IPv6使用相同的管理模式
- **安全的规则清理** - 不会误删系统原有的iptables规则
- **易于故障排除** - 所有规则都有明确的链标识

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

