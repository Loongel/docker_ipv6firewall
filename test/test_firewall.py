#!/usr/bin/env python3
"""
测试脚本
"""

import sys
import os
import subprocess
import time
import docker

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from config import Config
from firewall_manager import FirewallManager
from docker_monitor import DockerMonitor


def test_config():
    """测试配置加载"""
    print("测试配置加载...")
    config = Config()
    print(f"  父接口: {config.parent_interface}")
    print(f"  网关接口: {config.gateway_macvlan}")
    print(f"  监控网络: {config.monitored_networks}")
    print("✓ 配置加载成功")
    return True


def test_firewall_manager():
    """测试防火墙管理器"""
    print("\n测试防火墙管理器...")
    config = Config()
    fm = FirewallManager(config)
    
    try:
        # 测试初始化
        fm.initialize()
        print("✓ 防火墙管理器初始化成功")
        
        # 测试添加规则
        test_networks = {
            'macvlan_ipv6_swarm': {
                'GlobalIPv6Address': '2a0e:1d80:14:ccc4:ab00:1111:1000:99'
            }
        }
        test_ports = [{'port': 8080, 'protocol': 'tcp'}]
        
        fm.add_container_rules(
            'test_container_id',
            'test_container',
            test_ports,
            test_networks
        )
        print("✓ 添加测试规则成功")
        
        # 检查规则数量
        count = fm.get_active_rules_count()
        print(f"✓ 活跃规则数量: {count}")
        
        # 移除规则
        fm.remove_container_rules('test_container_id')
        print("✓ 移除测试规则成功")
        
    except Exception as e:
        print(f"✗ 防火墙管理器测试失败: {e}")
        return False
        
    return True


def test_docker_connection():
    """测试Docker连接"""
    print("\n测试Docker连接...")
    try:
        client = docker.DockerClient(base_url='unix:///var/run/docker.sock')
        client.ping()
        
        containers = client.containers.list()
        print(f"✓ Docker连接成功，发现 {len(containers)} 个运行中的容器")
        
        # 测试获取容器信息
        if containers:
            container = containers[0]
            print(f"  示例容器: {container.name}")
            
            # 获取inspect信息
            inspect_data = client.api.inspect_container(container.id)
            exposed_ports = inspect_data.get('Config', {}).get('ExposedPorts', {})
            networks = inspect_data.get('NetworkSettings', {}).get('Networks', {})
            
            print(f"  暴露端口: {list(exposed_ports.keys())}")
            print(f"  网络: {list(networks.keys())}")
            
        client.close()
        return True
        
    except Exception as e:
        print(f"✗ Docker连接测试失败: {e}")
        return False


def test_ip6tables():
    """测试ip6tables命令"""
    print("\n测试ip6tables...")
    try:
        # 检查ip6tables是否可用
        result = subprocess.run(['ip6tables', '--version'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ ip6tables版本: {result.stdout.strip()}")
        else:
            print("✗ ip6tables不可用")
            return False
            
        # 检查当前规则
        result = subprocess.run(['ip6tables', '-L', '-n'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ 可以读取ip6tables规则")
        else:
            print("✗ 无法读取ip6tables规则")
            return False
            
        return True
        
    except Exception as e:
        print(f"✗ ip6tables测试失败: {e}")
        return False


def main():
    """主测试函数"""
    print("Docker IPv6 Firewall Manager 测试")
    print("=" * 50)
    
    tests = [
        test_config,
        test_ip6tables,
        test_docker_connection,
        test_firewall_manager
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ 测试异常: {e}")
    
    print("\n" + "=" * 50)
    print(f"测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("✓ 所有测试通过！")
        return 0
    else:
        print("✗ 部分测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
