#!/bin/bash
set -e

# Docker IPv6 Firewall Manager 安装脚本
# 
# 用法：
#   sudo ./scripts/install.sh          # 标准安装
#   sudo ./scripts/install.sh --dev    # 开发模式安装

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DEV_MODE=false

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --dev)
            DEV_MODE=true
            shift
            ;;
        -h|--help)
            echo "Docker IPv6 Firewall Manager 安装脚本"
            echo ""
            echo "用法："
            echo "  sudo $0          # 标准安装"
            echo "  sudo $0 --dev    # 开发模式安装"
            echo "  sudo $0 --help   # 显示帮助"
            echo ""
            echo "标准安装：构建并安装 Debian 包"
            echo "开发模式：直接从源码安装，便于开发调试"
            exit 0
            ;;
        *)
            echo "未知参数: $1"
            echo "使用 --help 查看帮助"
            exit 1
            ;;
    esac
done

# 检查权限
if [[ $EUID -ne 0 ]]; then
   echo "错误: 此脚本需要 root 权限运行"
   echo "请使用: sudo $0"
   exit 1
fi

# 检查系统
if ! command -v systemctl &> /dev/null; then
    echo "错误: 系统不支持 systemd"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo "警告: Docker 未安装或未运行"
    echo "请确保 Docker 已正确安装并运行"
fi

echo "Docker IPv6 Firewall Manager 安装程序"
echo "========================================"
echo ""

# 安装依赖
echo "1. 安装系统依赖..."
apt-get update
apt-get install -y python3 python3-docker python3-yaml iptables systemd

if $DEV_MODE; then
    echo ""
    echo "2. 开发模式安装..."
    
    # 创建目录
    mkdir -p /usr/lib/docker-ipv6-firewall
    mkdir -p /etc/docker-ipv6-firewall
    mkdir -p /var/log
    
    # 复制源码
    cp "$PROJECT_DIR"/src/*.py /usr/lib/docker-ipv6-firewall/
    chmod 755 /usr/lib/docker-ipv6-firewall/main.py
    
    # 复制配置文件
    if [ ! -f /etc/docker-ipv6-firewall/config.yaml ]; then
        cp "$PROJECT_DIR/config/config.yaml" /etc/docker-ipv6-firewall/
        chmod 644 /etc/docker-ipv6-firewall/config.yaml
    else
        echo "配置文件已存在，跳过复制"
    fi
    
    # 复制服务文件
    cp "$PROJECT_DIR/systemd/docker-ipv6-firewall.service" /etc/systemd/system/
    
    # 创建日志文件
    touch /var/log/docker-ipv6-firewall.log
    chmod 644 /var/log/docker-ipv6-firewall.log
    
    echo "开发模式安装完成"
    
else
    echo ""
    echo "2. 构建 Debian 包..."
    cd "$PROJECT_DIR"
    ./build.sh
    
    echo ""
    echo "3. 安装 Debian 包..."
    dpkg -i docker-ipv6-firewall_*.deb || {
        echo "安装过程中遇到依赖问题，尝试修复..."
        apt-get install -f
    }
fi

echo ""
echo "4. 启用并启动服务..."

# 重新加载 systemd
systemctl daemon-reload

# 启用服务
systemctl enable docker-ipv6-firewall.service

# 检查 Docker 是否运行
if systemctl is-active --quiet docker; then
    systemctl start docker-ipv6-firewall.service
    echo "服务已启动"
else
    echo "Docker 未运行，服务将在 Docker 启动后自动启动"
fi

echo ""
echo "5. 验证安装..."

# 检查服务状态
if systemctl is-active --quiet docker-ipv6-firewall; then
    echo "✓ 服务运行正常"
else
    echo "⚠ 服务未运行，检查状态："
    systemctl status docker-ipv6-firewall --no-pager -l
fi

# 检查配置文件
if [ -f /etc/docker-ipv6-firewall/config.yaml ]; then
    echo "✓ 配置文件存在"
    if python3 -c "import yaml; yaml.safe_load(open('/etc/docker-ipv6-firewall/config.yaml'))" 2>/dev/null; then
        echo "✓ 配置文件语法正确"
    else
        echo "⚠ 配置文件语法错误"
    fi
else
    echo "✗ 配置文件不存在"
fi

# 检查日志文件
if [ -f /var/log/docker-ipv6-firewall.log ]; then
    echo "✓ 日志文件存在"
else
    echo "⚠ 日志文件不存在"
fi

echo ""
echo "安装完成！"
echo ""
echo "使用说明："
echo "  查看状态: systemctl status docker-ipv6-firewall"
echo "  查看日志: journalctl -u docker-ipv6-firewall -f"
echo "  查看规则: ip6tables -L DOCKER_IPV6_FORWARD -n -v"
echo "  编辑配置: nano /etc/docker-ipv6-firewall/config.yaml"
echo "  重启服务: systemctl restart docker-ipv6-firewall"
echo ""

if $DEV_MODE; then
    echo "开发模式提示："
    echo "  源码位置: /usr/lib/docker-ipv6-firewall/"
    echo "  修改源码后需要重启服务: systemctl restart docker-ipv6-firewall"
    echo ""
fi

echo "重要提醒："
echo "1. 请检查配置文件中的网络接口设置是否正确"
echo "2. 确保 parent_interface 和 gateway_macvlan 配置匹配您的网络环境"
echo "3. 服务会自动管理防火墙规则，请勿手动修改相关规则"
echo ""
