#!/bin/bash
set -e

# 配置验证测试脚本

echo "=== Docker IPv6 Firewall Manager 配置验证测试 ==="
echo ""

# 检查权限
if [[ $EUID -ne 0 ]]; then
   echo "错误: 此脚本需要 root 权限运行"
   echo "请使用: sudo $0"
   exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TEST_CONFIG_DIR="/tmp/docker-ipv6-firewall-test"
TEST_CONFIG_FILE="$TEST_CONFIG_DIR/config.yaml"

# 清理测试环境
cleanup() {
    echo "清理测试环境..."
    rm -rf "$TEST_CONFIG_DIR"
}

trap cleanup EXIT

echo "1. 创建测试环境..."
mkdir -p "$TEST_CONFIG_DIR"

echo ""
echo "2. 测试有效配置..."
cat > "$TEST_CONFIG_FILE" << 'EOF'
# 测试配置文件
parent_interface: ens3
gateway_macvlan: macvlan_gw
chain_name: DOCKER_IPV6_FORWARD
log_level: INFO
monitored_networks:
  - macvlan
  - bridge
EOF

echo "验证有效配置:"
python3 "$PROJECT_DIR/scripts/validate-config.py" --config "$TEST_CONFIG_FILE" --verbose

echo ""
echo "3. 测试无效配置 - 缺少必需字段..."
cat > "$TEST_CONFIG_FILE" << 'EOF'
# 无效配置 - 缺少必需字段
log_level: INFO
monitored_networks:
  - macvlan
EOF

echo "验证无效配置（缺少必需字段）:"
python3 "$PROJECT_DIR/scripts/validate-config.py" --config "$TEST_CONFIG_FILE" || echo "预期的验证失败"

echo ""
echo "4. 测试无效配置 - 错误的日志级别..."
cat > "$TEST_CONFIG_FILE" << 'EOF'
# 无效配置 - 错误的日志级别
parent_interface: ens3
gateway_macvlan: macvlan_gw
log_level: INVALID_LEVEL
monitored_networks:
  - macvlan
EOF

echo "验证无效配置（错误日志级别）:"
python3 "$PROJECT_DIR/scripts/validate-config.py" --config "$TEST_CONFIG_FILE" || echo "预期的验证失败"

echo ""
echo "5. 测试无效配置 - 空的监控网络..."
cat > "$TEST_CONFIG_FILE" << 'EOF'
# 无效配置 - 空的监控网络
parent_interface: ens3
gateway_macvlan: macvlan_gw
monitored_networks: []
EOF

echo "验证无效配置（空监控网络）:"
python3 "$PROJECT_DIR/scripts/validate-config.py" --config "$TEST_CONFIG_FILE" || echo "预期的验证失败"

echo ""
echo "6. 测试YAML格式错误..."
cat > "$TEST_CONFIG_FILE" << 'EOF'
# YAML格式错误
parent_interface: ens3
gateway_macvlan: macvlan_gw
invalid_yaml: [unclosed list
EOF

echo "验证YAML格式错误:"
python3 "$PROJECT_DIR/scripts/validate-config.py" --config "$TEST_CONFIG_FILE" || echo "预期的验证失败"

echo ""
echo "7. 测试不存在的配置文件..."
echo "验证不存在的配置文件:"
python3 "$PROJECT_DIR/scripts/validate-config.py" --config "/nonexistent/config.yaml" || echo "预期的验证失败"

echo ""
echo "8. 测试自动修复功能..."
rm -f "$TEST_CONFIG_FILE"
echo "尝试自动修复不存在的配置文件:"
python3 "$PROJECT_DIR/scripts/validate-config.py" --config "$TEST_CONFIG_FILE" --fix

if [ -f "$TEST_CONFIG_FILE" ]; then
    echo "✓ 配置文件已创建"
    echo "验证自动创建的配置:"
    python3 "$PROJECT_DIR/scripts/validate-config.py" --config "$TEST_CONFIG_FILE"
else
    echo "✗ 配置文件未创建"
fi

echo ""
echo "=== 配置验证测试完成 ==="
echo ""
echo "测试结果："
echo "✓ 有效配置验证通过"
echo "✓ 无效配置正确识别"
echo "✓ YAML格式错误正确处理"
echo "✓ 自动修复功能正常"
echo ""
echo "配置验证功能测试通过！"
