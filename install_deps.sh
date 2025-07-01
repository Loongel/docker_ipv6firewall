#!/bin/bash
set -e

echo "安装Docker IPv6 Firewall Manager依赖..."

# 更新包列表
apt-get update

# 安装Python依赖
echo "安装Python依赖..."
apt-get install -y python3 python3-pip python3-yaml

# 安装Docker Python库
pip3 install docker

# 确保iptables已安装
echo "检查iptables..."
apt-get install -y iptables

# 检查systemd
echo "检查systemd..."
if ! systemctl --version > /dev/null 2>&1; then
    echo "错误: systemd未安装或不可用"
    exit 1
fi

echo "依赖安装完成！"
echo ""
echo "现在可以运行测试:"
echo "python3 test/test_firewall.py"
echo ""
echo "或构建包:"
echo "./build.sh"
