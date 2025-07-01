#!/bin/bash
set -e

# Docker IPv6 Firewall Manager 卸载脚本

# 检查权限
if [[ $EUID -ne 0 ]]; then
   echo "错误: 此脚本需要 root 权限运行"
   echo "请使用: sudo $0"
   exit 1
fi

echo "Docker IPv6 Firewall Manager 卸载程序"
echo "========================================"
echo ""

# 解析命令行参数
PURGE=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --purge)
            PURGE=true
            shift
            ;;
        -h|--help)
            echo "用法："
            echo "  sudo $0          # 标准卸载（保留配置文件）"
            echo "  sudo $0 --purge  # 完全卸载（删除所有文件）"
            exit 0
            ;;
        *)
            echo "未知参数: $1"
            exit 1
            ;;
    esac
done

echo "1. 停止服务..."
if systemctl is-active --quiet docker-ipv6-firewall; then
    systemctl stop docker-ipv6-firewall
    echo "服务已停止"
else
    echo "服务未运行"
fi

echo ""
echo "2. 禁用服务..."
if systemctl is-enabled --quiet docker-ipv6-firewall; then
    systemctl disable docker-ipv6-firewall
    echo "服务已禁用"
else
    echo "服务未启用"
fi

echo ""
echo "3. 清理防火墙规则..."
# 尝试清理我们创建的防火墙链
if ip6tables -L DOCKER_IPV6_FORWARD >/dev/null 2>&1; then
    echo "发现防火墙链，正在清理..."
    
    # 删除 FORWARD 链中对我们链的引用
    ip6tables -D FORWARD -j DOCKER_IPV6_FORWARD 2>/dev/null || true
    
    # 清空我们的链
    ip6tables -F DOCKER_IPV6_FORWARD 2>/dev/null || true
    
    # 删除我们的链
    ip6tables -X DOCKER_IPV6_FORWARD 2>/dev/null || true
    
    echo "防火墙规则已清理"
else
    echo "未发现防火墙链"
fi

echo ""
echo "4. 卸载软件包..."
if dpkg -l | grep -q docker-ipv6-firewall; then
    if $PURGE; then
        dpkg --purge docker-ipv6-firewall
        echo "软件包已完全删除"
    else
        dpkg -r docker-ipv6-firewall
        echo "软件包已删除（配置文件保留）"
    fi
else
    echo "软件包未安装或已删除"
fi

echo ""
echo "5. 清理文件..."

# 删除服务文件
if [ -f /etc/systemd/system/docker-ipv6-firewall.service ]; then
    rm -f /etc/systemd/system/docker-ipv6-firewall.service
    echo "服务文件已删除"
fi

# 删除程序文件
if [ -d /usr/lib/docker-ipv6-firewall ]; then
    rm -rf /usr/lib/docker-ipv6-firewall
    echo "程序文件已删除"
fi

if $PURGE; then
    # 完全删除模式
    if [ -d /etc/docker-ipv6-firewall ]; then
        rm -rf /etc/docker-ipv6-firewall
        echo "配置文件已删除"
    fi
    
    if [ -f /var/log/docker-ipv6-firewall.log ]; then
        rm -f /var/log/docker-ipv6-firewall.log
        echo "日志文件已删除"
    fi
else
    # 标准删除模式，保留配置
    if [ -d /etc/docker-ipv6-firewall ]; then
        echo "配置文件保留在 /etc/docker-ipv6-firewall/"
    fi
    
    if [ -f /var/log/docker-ipv6-firewall.log ]; then
        echo "日志文件保留在 /var/log/docker-ipv6-firewall.log"
    fi
fi

echo ""
echo "6. 重新加载 systemd..."
systemctl daemon-reload

echo ""
echo "卸载完成！"
echo ""

if $PURGE; then
    echo "所有文件已删除"
else
    echo "配置文件和日志已保留"
    echo "如需完全删除，请使用: sudo $0 --purge"
fi

echo ""
echo "注意："
echo "1. 如果您手动修改过系统防火墙规则，请检查是否需要手动清理"
echo "2. 如果您使用了自定义配置，相关的网络设置不会被自动恢复"
echo ""
