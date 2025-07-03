#!/usr/bin/env python3
"""
配置管理模块
"""

import yaml
import os
import logging
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple


@dataclass
class Config:
    """配置类"""

    # 默认配置
    config_file: str = "/etc/docker-ipv6-firewall/config.yaml"
    log_file: str = "/var/log/docker-ipv6-firewall.log"
    log_level: str = "INFO"

    # 网络接口配置（核心配置）
    parent_interface: str = "ens3"        # 物理网络接口
    gateway_macvlan: str = "macvlan_gw"   # macvlan网关接口

    # Docker配置
    docker_socket: str = "unix:///var/run/docker.sock"

    # 防火墙配置
    # IPv6专用链
    chain_name: str = "DOCKER_IPV6FW_FORWARD"          # IPv6主要FORWARD链名称
    input_chain_name: str = "DOCKER_IPV6FW_INPUT"      # IPv6基础协议链名称
    nat_chain_name: str = "DOCKER_IPV6FW_NAT"          # IPv6 NAT规则链名称

    # IPv4专用链
    ipv4_chain_name: str = "DOCKER_IPV4FW_FORWARD"     # IPv4主要FORWARD链名称
    ipv4_nat_chain_name: str = "DOCKER_IPV4FW_NAT"     # IPv4 NAT规则链名称

    # 命令路径
    ip6tables_cmd: str = "ip6tables"                    # ip6tables命令路径
    iptables_cmd: str = "iptables"                      # iptables命令路径
    ipv6_link_local: str = "fe80::/10"                  # IPv6链路本地地址范围

    # 监控的网络类型
    monitored_networks: List[str] = None

    # 内部状态
    _config_mtime: float = 0
    _validation_errors: List[str] = None
    _is_valid: bool = True

    def __post_init__(self):
        """初始化后处理"""
        if self.monitored_networks is None:
            self.monitored_networks = ["macvlan", "bridge"]
        self._validation_errors = []
        self.load_config()
        
    def load_config(self):
        """加载配置文件"""
        self._validation_errors = []
        self._is_valid = True

        if not os.path.exists(self.config_file):
            self._add_validation_error(f"配置文件不存在: {self.config_file}")
            return

        try:
            # 记录文件修改时间
            self._config_mtime = os.path.getmtime(self.config_file)

            with open(self.config_file, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)

            if config_data:
                # 验证配置数据
                if self._validate_config_data(config_data):
                    # 更新配置
                    for key, value in config_data.items():
                        if hasattr(self, key):
                            setattr(self, key, value)

                    # 验证配置的有效性
                    self._validate_config()
                else:
                    self._is_valid = False
            else:
                self._add_validation_error("配置文件为空或格式错误")

        except yaml.YAMLError as e:
            self._add_validation_error(f"YAML格式错误: {e}")
        except Exception as e:
            self._add_validation_error(f"无法加载配置文件: {e}")
                
    def save_default_config(self):
        """保存默认配置文件"""
        config_dir = Path(self.config_file).parent
        config_dir.mkdir(parents=True, exist_ok=True)
        
        default_config = {
            'log_level': self.log_level,
            'log_file': self.log_file,
            'parent_interface': self.parent_interface,
            'gateway_macvlan': self.gateway_macvlan,
            'docker_socket': self.docker_socket,
            'chain_name': self.chain_name,
            'input_chain_name': self.input_chain_name,
            'nat_chain_name': self.nat_chain_name,
            'ipv4_chain_name': self.ipv4_chain_name,
            'ipv4_nat_chain_name': self.ipv4_nat_chain_name,
            'monitored_networks': self.monitored_networks
        }
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(default_config, f, default_flow_style=False, 
                         allow_unicode=True, indent=2)
        except Exception as e:
            print(f"警告: 无法保存配置文件 {self.config_file}: {e}")

    def _add_validation_error(self, error: str):
        """添加验证错误"""
        self._validation_errors.append(error)
        self._is_valid = False

    def _validate_config_data(self, config_data: Dict[str, Any]) -> bool:
        """验证配置数据格式"""
        valid = True

        # 检查必需的配置项
        required_fields = ['parent_interface', 'gateway_macvlan']
        for field in required_fields:
            if field not in config_data:
                self._add_validation_error(f"缺少必需配置项: {field}")
                valid = False
            elif not config_data[field] or not isinstance(config_data[field], str):
                self._add_validation_error(f"配置项 {field} 必须是非空字符串")
                valid = False

        # 检查日志级别
        if 'log_level' in config_data:
            valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            if config_data['log_level'].upper() not in valid_levels:
                self._add_validation_error(f"无效的日志级别: {config_data['log_level']}")
                valid = False

        # 检查监控网络类型
        if 'monitored_networks' in config_data:
            if not isinstance(config_data['monitored_networks'], list):
                self._add_validation_error("monitored_networks 必须是列表")
                valid = False
            elif not config_data['monitored_networks']:
                self._add_validation_error("monitored_networks 不能为空")
                valid = False

        return valid

    def _validate_config(self):
        """验证配置的实际有效性"""
        # 检查网络接口是否存在
        if not self._check_interface_exists(self.parent_interface):
            self._add_validation_error(f"物理接口不存在: {self.parent_interface}")

        if not self._check_interface_exists(self.gateway_macvlan):
            self._add_validation_error(f"macvlan网关接口不存在: {self.gateway_macvlan}")

        # 检查Docker socket
        if not os.path.exists(self.docker_socket.replace('unix://', '')):
            self._add_validation_error(f"Docker socket不存在: {self.docker_socket}")

        # 检查日志目录权限
        log_dir = os.path.dirname(self.log_file)
        if not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir, exist_ok=True)
            except Exception as e:
                self._add_validation_error(f"无法创建日志目录 {log_dir}: {e}")
        elif not os.access(log_dir, os.W_OK):
            self._add_validation_error(f"日志目录无写权限: {log_dir}")

    def _check_interface_exists(self, interface: str) -> bool:
        """检查网络接口是否存在"""
        try:
            result = subprocess.run(['ip', 'link', 'show', interface],
                                  capture_output=True, text=True)
            return result.returncode == 0
        except Exception:
            return False

    def is_valid(self) -> bool:
        """检查配置是否有效"""
        return self._is_valid

    def get_validation_errors(self) -> List[str]:
        """获取验证错误列表"""
        return self._validation_errors.copy()

    def has_config_changed(self) -> bool:
        """检查配置文件是否已修改"""
        if not os.path.exists(self.config_file):
            return False
        try:
            current_mtime = os.path.getmtime(self.config_file)
            return current_mtime > self._config_mtime
        except Exception:
            return False

    def reload_config(self) -> Tuple[bool, List[str]]:
        """重新加载配置文件"""
        old_errors = self._validation_errors.copy()
        self.load_config()

        # 返回是否成功和错误信息
        return self._is_valid, self._validation_errors

    def get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要"""
        return {
            'parent_interface': self.parent_interface,
            'gateway_macvlan': self.gateway_macvlan,
            'chain_name': self.chain_name,
            'monitored_networks': self.monitored_networks,
            'log_level': self.log_level,
            'docker_socket': self.docker_socket,
            'is_valid': self._is_valid,
            'validation_errors': self._validation_errors
        }
