#!/usr/bin/env python3
"""
配置验证工具
"""

import sys
import os
import argparse

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from config import Config


def main():
    parser = argparse.ArgumentParser(description='Docker IPv6 Firewall Manager 配置验证工具')
    parser.add_argument('--config', '-c', 
                       default='/etc/docker-ipv6-firewall/config.yaml',
                       help='配置文件路径')
    parser.add_argument('--fix', '-f', action='store_true',
                       help='尝试自动修复一些问题')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='详细输出')
    
    args = parser.parse_args()
    
    print("Docker IPv6 Firewall Manager 配置验证工具")
    print("=" * 50)
    print(f"配置文件: {args.config}")
    print("")
    
    # 创建配置对象
    config = Config()
    config.config_file = args.config
    config.load_config()
    
    # 显示配置摘要
    if args.verbose:
        print("配置摘要:")
        summary = config.get_config_summary()
        for key, value in summary.items():
            if key not in ['is_valid', 'validation_errors']:
                print(f"  {key}: {value}")
        print("")
    
    # 检查配置有效性
    if config.is_valid():
        print("✓ 配置验证通过")
        print("")
        print("配置详情:")
        print(f"  物理接口: {config.parent_interface}")
        print(f"  网关接口: {config.gateway_macvlan}")
        print(f"  防火墙链: {config.chain_name}")
        print(f"  监控网络: {', '.join(config.monitored_networks)}")
        print(f"  日志级别: {config.log_level}")
        print("")
        return 0
    else:
        print("✗ 配置验证失败")
        print("")
        print("错误详情:")
        for error in config.get_validation_errors():
            print(f"  - {error}")
        print("")
        
        if args.fix:
            print("尝试自动修复...")
            fixed = try_auto_fix(config)
            if fixed:
                print("✓ 部分问题已修复，请重新验证配置")
            else:
                print("✗ 无法自动修复，请手动修复配置")
        else:
            print("使用 --fix 参数尝试自动修复")
            
        return 1


def try_auto_fix(config):
    """尝试自动修复配置问题"""
    fixed = False
    
    # 检查并创建日志目录
    log_dir = os.path.dirname(config.log_file)
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True)
            print(f"  ✓ 创建日志目录: {log_dir}")
            fixed = True
        except Exception as e:
            print(f"  ✗ 无法创建日志目录: {e}")
    
    # 检查并创建配置目录
    config_dir = os.path.dirname(config.config_file)
    if not os.path.exists(config_dir):
        try:
            os.makedirs(config_dir, exist_ok=True)
            print(f"  ✓ 创建配置目录: {config_dir}")
            fixed = True
        except Exception as e:
            print(f"  ✗ 无法创建配置目录: {e}")
    
    # 如果配置文件不存在，创建默认配置
    if not os.path.exists(config.config_file):
        try:
            config.save_default_config()
            print(f"  ✓ 创建默认配置文件: {config.config_file}")
            fixed = True
        except Exception as e:
            print(f"  ✗ 无法创建配置文件: {e}")
    
    return fixed


if __name__ == "__main__":
    sys.exit(main())
