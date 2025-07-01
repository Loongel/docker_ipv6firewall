#!/bin/bash
set -e

# Docker IPv6 Firewall Manager 管理工具

CHAIN_NAME="DOCKER_IPV6_FORWARD"
SERVICE_NAME="docker-ipv6-firewall"

show_help() {
    echo "Docker IPv6 Firewall Manager 管理工具"
    echo ""
    echo "用法: $0 <命令>"
    echo ""
    echo "命令:"
    echo "  status          - 显示服务和防火墙状态"
    echo "  rules           - 显示当前防火墙规则"
    echo "  clean           - 清理所有防火墙规则"
    echo "  reset           - 重置服务（停止、清理、启动）"
    echo "  sync            - 检查规则一致性"
    echo "  logs            - 显示服务日志"
    echo "  config          - 验证配置文件"
    echo "  reload          - 重新加载配置（热重载）"
    echo "  help            - 显示此帮助"
    echo ""
}

show_status() {
    echo "=== 服务状态 ==="
    if systemctl is-active --quiet $SERVICE_NAME; then
        echo "✓ 服务运行中"
    else
        echo "✗ 服务未运行"
    fi
    
    if systemctl is-enabled --quiet $SERVICE_NAME; then
        echo "✓ 开机自启动已启用"
    else
        echo "✗ 开机自启动未启用"
    fi
    
    echo ""
    echo "=== Docker 状态 ==="
    if systemctl is-active --quiet docker; then
        echo "✓ Docker 运行中"
        docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | head -10
    else
        echo "✗ Docker 未运行"
    fi
    
    echo ""
    echo "=== 防火墙状态 ==="
    show_rules
}

show_rules() {
    if ip6tables -L $CHAIN_NAME -n -v >/dev/null 2>&1; then
        echo "防火墙链 $CHAIN_NAME 存在："
        ip6tables -L $CHAIN_NAME -n -v --line-numbers
        
        # 统计规则
        rule_count=$(ip6tables -L $CHAIN_NAME -n | grep -c "tcp dpt:" || echo "0")
        echo ""
        echo "容器规则数量: $rule_count"
    else
        echo "防火墙链 $CHAIN_NAME 不存在"
    fi
}

clean_rules() {
    echo "清理防火墙规则..."

    # 使用项目代码进行清理
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

    if [ -f "$PROJECT_DIR/src/firewall_manager.py" ]; then
        echo "使用项目清理代码..."
        python3 -c "
import sys
sys.path.insert(0, '$PROJECT_DIR/src')
from config import Config
from firewall_manager import FirewallManager

config = Config()
fm = FirewallManager(config)

print(f'清理防火墙链: {config.chain_name}')
fm._remove_chain_completely()
fm._cleanup_ipv6_base_rules()
print('✓ 项目代码清理完成')
" 2>/dev/null && echo "✓ 使用项目代码清理成功" || {
        echo "项目代码清理失败，使用基本清理..."

        # 基本清理（从配置读取链名称）
        if [ -f /etc/docker-ipv6-firewall/config.yaml ]; then
            CHAIN_NAME=$(python3 -c "
import yaml
try:
    with open('/etc/docker-ipv6-firewall/config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    print(config.get('chain_name', 'DOCKER_IPV6_FORWARD'))
except:
    print('DOCKER_IPV6_FORWARD')
" 2>/dev/null || echo "DOCKER_IPV6_FORWARD")
        fi

        echo "清理防火墙链: $CHAIN_NAME"
        ip6tables -D FORWARD -j $CHAIN_NAME 2>/dev/null && echo "✓ 已从FORWARD链中删除引用" || true
        ip6tables -F $CHAIN_NAME 2>/dev/null && echo "✓ 已清空链 $CHAIN_NAME" || true
        ip6tables -X $CHAIN_NAME 2>/dev/null && echo "✓ 已删除链 $CHAIN_NAME" || true
        echo "✓ 基本清理完成"
    }
    else
        echo "项目文件不存在，使用基本清理..."
        ip6tables -D FORWARD -j $CHAIN_NAME 2>/dev/null && echo "✓ 已从FORWARD链中删除引用" || true
        ip6tables -F $CHAIN_NAME 2>/dev/null && echo "✓ 已清空链 $CHAIN_NAME" || true
        ip6tables -X $CHAIN_NAME 2>/dev/null && echo "✓ 已删除链 $CHAIN_NAME" || true
    fi

    echo "防火墙规则清理完成"
}

reset_service() {
    echo "重置服务..."
    
    # 停止服务
    if systemctl is-active --quiet $SERVICE_NAME; then
        echo "停止服务..."
        systemctl stop $SERVICE_NAME
    fi
    
    # 清理规则
    clean_rules
    
    # 启动服务
    echo "启动服务..."
    systemctl start $SERVICE_NAME
    
    # 等待一下
    sleep 2
    
    # 检查状态
    if systemctl is-active --quiet $SERVICE_NAME; then
        echo "✓ 服务重置成功"
    else
        echo "✗ 服务启动失败"
        systemctl status $SERVICE_NAME --no-pager -l
    fi
}

check_sync() {
    echo "检查规则一致性..."
    
    if ! systemctl is-active --quiet $SERVICE_NAME; then
        echo "✗ 服务未运行，无法检查一致性"
        return 1
    fi
    
    # 获取防火墙中的容器规则数量
    if ip6tables -L $CHAIN_NAME -n >/dev/null 2>&1; then
        fw_rules=$(ip6tables -L $CHAIN_NAME -n | grep -c "tcp dpt:" || echo "0")
    else
        fw_rules=0
    fi
    
    # 获取运行中的容器数量（有暴露端口的）
    running_containers=$(docker ps --format "{{.Names}}" | wc -l)
    
    echo "防火墙中的容器规则: $fw_rules"
    echo "运行中的容器: $running_containers"
    
    if [ "$fw_rules" -eq 0 ] && [ "$running_containers" -gt 0 ]; then
        echo "⚠ 可能存在不一致：有运行中的容器但没有防火墙规则"
        echo "建议运行: $0 reset"
    elif [ "$fw_rules" -gt 0 ] && [ "$running_containers" -eq 0 ]; then
        echo "⚠ 可能存在不一致：有防火墙规则但没有运行中的容器"
        echo "建议运行: $0 reset"
    else
        echo "✓ 状态看起来正常"
    fi
}

show_logs() {
    echo "=== 最近的服务日志 ==="
    journalctl -u $SERVICE_NAME --no-pager -l -n 20

    echo ""
    echo "=== 实时日志（Ctrl+C 退出） ==="
    journalctl -u $SERVICE_NAME -f
}

validate_config() {
    echo "验证配置文件..."

    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    CONFIG_VALIDATOR="$SCRIPT_DIR/validate-config.py"

    if [ -f "$CONFIG_VALIDATOR" ]; then
        python3 "$CONFIG_VALIDATOR" --verbose
    else
        echo "配置验证工具不存在: $CONFIG_VALIDATOR"
        return 1
    fi
}

reload_config() {
    echo "重新加载配置..."

    if ! systemctl is-active --quiet $SERVICE_NAME; then
        echo "✗ 服务未运行，无法重新加载配置"
        return 1
    fi

    # 发送SIGHUP信号触发配置重载
    echo "发送重载信号到服务..."
    systemctl reload $SERVICE_NAME 2>/dev/null || {
        echo "服务不支持reload，尝试重启..."
        systemctl restart $SERVICE_NAME
    }

    # 等待一下
    sleep 2

    # 检查服务状态
    if systemctl is-active --quiet $SERVICE_NAME; then
        echo "✓ 配置重新加载成功"

        # 检查最近的日志
        echo ""
        echo "最近的日志:"
        journalctl -u $SERVICE_NAME --since "30 seconds ago" --no-pager -l
    else
        echo "✗ 服务重启失败"
        systemctl status $SERVICE_NAME --no-pager -l
        return 1
    fi
}

# 检查权限
if [[ $EUID -ne 0 ]]; then
   echo "错误: 此脚本需要 root 权限运行"
   echo "请使用: sudo $0 $*"
   exit 1
fi

# 解析命令
case "${1:-help}" in
    status)
        show_status
        ;;
    rules)
        show_rules
        ;;
    clean)
        clean_rules
        ;;
    reset)
        reset_service
        ;;
    sync)
        check_sync
        ;;
    logs)
        show_logs
        ;;
    config)
        validate_config
        ;;
    reload)
        reload_config
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "未知命令: $1"
        echo ""
        show_help
        exit 1
        ;;
esac
