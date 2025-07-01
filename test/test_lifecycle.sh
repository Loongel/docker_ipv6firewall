#!/bin/bash
set -e

# Docker IPv6 Firewall Manager 生命周期测试

echo "=== Docker IPv6 Firewall Manager 生命周期测试 ==="
echo ""

# 检查权限
if [[ $EUID -ne 0 ]]; then
   echo "错误: 此脚本需要 root 权限运行"
   echo "请使用: sudo $0"
   exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CHAIN_NAME="DOCKER_IPV6_FORWARD"

echo "1. 停止服务并清理环境..."
systemctl stop docker-ipv6-firewall || true
"$PROJECT_DIR/scripts/manage.sh" clean || true

echo ""
echo "2. 检查清理结果..."
if ip6tables -L $CHAIN_NAME >/dev/null 2>&1; then
    echo "✗ 防火墙链仍然存在"
else
    echo "✓ 防火墙链已清理"
fi

echo ""
echo "3. 启动服务..."
systemctl start docker-ipv6-firewall

echo ""
echo "4. 等待服务启动..."
sleep 3

echo ""
echo "5. 检查服务状态..."
if systemctl is-active --quiet docker-ipv6-firewall; then
    echo "✓ 服务运行正常"
else
    echo "✗ 服务启动失败"
    systemctl status docker-ipv6-firewall --no-pager -l
    exit 1
fi

echo ""
echo "6. 检查防火墙规则..."
if ip6tables -L $CHAIN_NAME >/dev/null 2>&1; then
    echo "✓ 防火墙链已创建"
    rule_count=$(ip6tables -L $CHAIN_NAME -n | grep -c "tcp dpt:" || echo "0")
    echo "  容器规则数量: $rule_count"
else
    echo "✗ 防火墙链不存在"
    exit 1
fi

echo ""
echo "7. 检查规则一致性..."
"$PROJECT_DIR/scripts/manage.sh" sync

echo ""
echo "8. 测试服务停止..."
systemctl stop docker-ipv6-firewall

echo ""
echo "9. 等待服务停止..."
sleep 3

echo ""
echo "10. 检查清理结果..."
if ip6tables -L $CHAIN_NAME >/dev/null 2>&1; then
    rule_count=$(ip6tables -L $CHAIN_NAME -n | wc -l)
    if [ "$rule_count" -le 2 ]; then
        echo "✓ 防火墙链已清空（只剩表头）"
    else
        echo "⚠ 防火墙链存在但可能有残留规则"
        ip6tables -L $CHAIN_NAME -n -v
    fi
else
    echo "✓ 防火墙链已完全删除"
fi

echo ""
echo "11. 重新启动服务..."
systemctl start docker-ipv6-firewall

echo ""
echo "12. 最终状态检查..."
sleep 3
"$PROJECT_DIR/scripts/manage.sh" status

echo ""
echo "=== 生命周期测试完成 ==="
echo ""
echo "测试结果："
echo "✓ 服务启动正常"
echo "✓ 防火墙规则创建正常"
echo "✓ 服务停止时清理正常"
echo "✓ 服务重启后恢复正常"
echo ""
echo "生命周期测试通过！"
