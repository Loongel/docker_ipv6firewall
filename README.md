# Docker IPv6 Firewall Manager

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Debian 12](https://img.shields.io/badge/debian-12-red.svg)](https://www.debian.org/)

一个专门为 Docker macvlan 网络架构设计的 IPv6 防火墙自动管理工具。

## ⚠️ 重要说明

**此工具专门针对特定的网络架构设计：**

```
外网 (Internet) → 物理接口 (ens3) → macvlan网关 (macvlan_gw) → Docker容器
```

**适用场景：**
- 使用 macvlan 网络的 Docker 容器
- 需要从外网直接访问容器服务
- 有明确的物理接口和 macvlan 网关配置

**不适用场景：**
- 标准的 Docker bridge 网络（除非有 IPv6 配置）
- 复杂的多网卡环境
- 需要复杂路由策略的场景

## 功能特性

- 🔥 **自动监控** - 实时监控Docker容器启动/停止事件
- 🔍 **智能解析** - 自动解析容器的端口暴露信息和网络配置
- ⚡ **动态管理** - 实时添加/删除IPv6防火墙规则（ip6tables）
- 🛡️ **防重复** - 智能检测避免重复规则添加
- 🌐 **网络支持** - 专门支持macvlan网络，兼容bridge网络
- 🔧 **系统集成** - 完整的systemd服务集成
- 📦 **简易安装** - 专业的Debian包安装

## 系统要求

- **操作系统**: Debian 12 或兼容系统
- **容器**: Docker Engine (支持 IPv6)
- **网络**: ip6tables, macvlan 网络配置
- **系统**: systemd
- **运行时**: Python 3.9+

## 快速开始

### 方法一：使用安装脚本（推荐）

```bash
# 克隆项目
git clone https://github.com/Loongel/docker_ipv6firewall.git 
cd docker_ipv6firewall 

# 运行安装脚本
chmod +x build.sh ./scripts/install.sh 
sudo ./scripts/install.sh

# 配置参数
  编辑配置: nano /etc/docker-ipv6-firewall/config.yaml
  重启服务: systemctl restart docker-ipv6-firewall

# 检查状态
  查看状态: systemctl status docker-ipv6-firewall
  查看日志: journalctl -u docker-ipv6-firewall -f
  查看规则: ip6tables -L DOCKER_IPV6_FORWARD -n -v
```

### 方法二：手动构建安装

```bash
# 构建 Debian 包
make build

# 安装
sudo dpkg -i docker-ipv6-firewall_$(cat VERSION)_amd64.deb

# 如果有依赖问题
sudo apt-get install -f
```

### 方法三：开发模式安装

```bash
# 开发模式安装（便于调试）
sudo ./scripts/install.sh --dev
```

## 配置

### ⚠️ 重要：网络接口配置

**在使用前，必须正确配置网络接口！**

编辑配置文件：
```bash
sudo nano /etc/docker-ipv6-firewall/config.yaml
```

**核心配置项：**
```yaml
# 网络接口配置（必须正确设置）
parent_interface: ens3        # 您的物理网络接口
gateway_macvlan: macvlan_gw   # 您的 macvlan 网关接口

# 防火墙配置
chain_name: DOCKER_IPV6_FORWARD

# 监控的网络类型
monitored_networks:
  - macvlan              # 主要目标
  - bridge               # 如果有 IPv6 配置
```

### 如何确定正确的接口名称

```bash
# 查看网络接口
ip link show

# 查看 Docker 网络
docker network ls
docker network inspect <network_name>

# 查看当前防火墙规则
ip6tables -L -n -v
```

### 修改配置后重启服务
```bash
sudo systemctl restart docker-ipv6-firewall
```

## 使用方法

### 查看服务状态
```bash
sudo systemctl status docker-ipv6-firewall
```

### 查看实时日志
```bash
sudo journalctl -u docker-ipv6-firewall -f
```

### 查看防火墙规则
```bash
sudo ip6tables -L DOCKER_IPV6_FORWARD -n -v
```

### 使用管理工具（推荐）
```bash
# 查看完整状态
sudo ./scripts/manage.sh status

# 检查规则一致性
sudo ./scripts/manage.sh sync

# 重置服务（清理+重启）
sudo ./scripts/manage.sh reset

# 仅清理防火墙规则
sudo ./scripts/manage.sh clean

# 验证配置文件
sudo ./scripts/manage.sh config

# 热重载配置
sudo ./scripts/manage.sh reload

# 查看实时日志
sudo ./scripts/manage.sh logs
```

### 配置管理
```bash
# 验证配置文件
sudo python3 scripts/validate-config.py --verbose

# 自动修复配置问题
sudo python3 scripts/validate-config.py --fix

# 热重载配置（无需重启服务）
sudo systemctl reload docker-ipv6-firewall
```

### 手动重启服务
```bash
sudo systemctl restart docker-ipv6-firewall
```

## 工作原理

### 防火墙策略逻辑

**基础转发规则**（服务启动时自动添加）：
```bash
# 允许 macvlan_gw → ens3 转发（容器访问外网）
ip6tables -A DOCKER_IPV6_FORWARD -i macvlan_gw -o ens3 -j ACCEPT

# 允许 ens3 → macvlan_gw 转发（外网访问容器）
ip6tables -A DOCKER_IPV6_FORWARD -i ens3 -o macvlan_gw -j ACCEPT
```

**容器特定规则**（容器启动时动态添加）：
```bash
# 允许外网访问容器的特定端口
ip6tables -A DOCKER_IPV6_FORWARD -p tcp -d <容器IPv6> --dport <端口> -i ens3 -o macvlan_gw -j ACCEPT
```

### 工作流程

1. **服务启动** - 初始化防火墙链，添加基础转发规则
2. **容器监控** - 监听Docker事件API，获取容器生命周期事件
3. **信息解析** - 提取容器的端口暴露(`ExposedPorts`)和IPv6地址
4. **规则管理** - 动态添加/删除防火墙规则
5. **重复检测** - 避免重复规则，确保系统稳定

## 示例场景

当你启动一个nginx容器：
```bash
docker run -d --name web-server --network macvlan_ipv6_swarm nginx:alpine
```

服务会自动：
1. 检测到容器启动事件
2. 解析容器的端口80暴露配置
3. 获取容器的IPv6地址
4. 添加防火墙规则允许访问该容器的80端口

当容器停止时，对应的防火墙规则会自动删除。

## 故障排除

### 服务无法启动
```bash
# 检查Docker是否运行
sudo systemctl status docker

# 检查配置文件语法
sudo python3 -c "import yaml; yaml.safe_load(open('/etc/docker-ipv6-firewall/config.yaml'))"

# 查看详细错误日志
sudo journalctl -u docker-ipv6-firewall --no-pager -l
```

### 规则未生效
```bash
# 检查容器是否在监控的网络类型中
docker inspect <container_name> | grep NetworkMode

# 检查容器是否有暴露端口
docker inspect <container_name> | grep ExposedPorts

# 手动检查防火墙规则
sudo ip6tables -L DOCKER_IPV6_FORWARD -n -v
```

## 卸载

### 使用卸载脚本（推荐）
```bash
# 标准卸载（保留配置文件）
sudo ./scripts/uninstall.sh

# 完全卸载（删除所有文件）
sudo ./scripts/uninstall.sh --purge
```

### 手动卸载
```bash
# 停止并禁用服务
sudo systemctl stop docker-ipv6-firewall
sudo systemctl disable docker-ipv6-firewall

# 卸载包
sudo dpkg -r docker-ipv6-firewall

# 完全清理（包括配置文件）
sudo dpkg --purge docker-ipv6-firewall
```

### 使用 Makefile
```bash
# 卸载
make uninstall
```

## 项目结构

```
docker-ipv6-firewall/
├── src/                    # 源代码
│   ├── main.py            # 主服务程序
│   ├── docker_monitor.py  # Docker事件监控
│   ├── firewall_manager.py # 防火墙规则管理
│   └── config.py          # 配置管理
├── config/                # 配置文件
│   └── config.yaml        # 默认配置
├── systemd/               # 系统服务
│   └── docker-ipv6-firewall.service
├── debian/                # Debian包构建
│   ├── control           # 包信息
│   ├── postinst          # 安装后脚本
│   ├── prerm             # 卸载前脚本
│   └── postrm            # 卸载后脚本
├── scripts/               # 工具脚本
│   ├── install.sh        # 安装脚本
│   └── uninstall.sh      # 卸载脚本
├── test/                  # 测试文件
│   └── test_firewall.py  # 功能测试
├── docs/                  # 文档
│   ├── ARCHITECTURE.md   # 技术架构文档
│   ├── CONTRIBUTING.md   # 贡献指南
│   └── CHANGELOG.md      # 变更日志
├── Makefile              # 构建工具
├── build.sh              # 构建脚本
└── README.md             # 项目说明
```

## 开发和构建

### 快速开始
```bash
# 安装依赖
make deps

# 运行测试
make test

# 构建包和版本管理
# 开发新功能时：无需关心版本号
# 准备发布时：
make version-bump-minor 
# 或 
make version-bump-patch

# 构建发布：
make build # 自动使用正确版本号

# 版本追踪：
# CHANGELOG.md自动维护版本历史
```

# 安装
make install
```

### 手动操作
```bash
# 安装开发依赖
sudo apt-get install python3-docker python3-yaml

# 运行测试
python3 test/test_firewall.py

# 构建Debian包
./build.sh
```

## 日志示例

正常运行时的日志：
```
2025-06-30 16:53:13 - INFO - 启动 Docker IPv6 Firewall Manager
2025-06-30 16:53:13 - INFO - Docker连接成功
2025-06-30 16:53:13 - INFO - 发现 3 个运行中的容器
2025-06-30 16:53:13 - INFO - 处理容器启动: test_web_macvlan
2025-06-30 16:53:13 - INFO - 添加防火墙规则: test_web_macvlan:tcp/80 -> 2a0e:1d80:14:ccc4:ab00:1111:1000:3
2025-06-30 16:53:13 - INFO - 为容器 test_web_macvlan 添加了 1 条规则
```
