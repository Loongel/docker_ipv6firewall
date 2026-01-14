#!/usr/bin/env python3
"""
防火墙管理模块
"""

import subprocess
import logging
import re
from typing import List, Dict, Set, Tuple
from dataclasses import dataclass


@dataclass
class FirewallRule:
    """容器防火墙规则"""
    container_id: str
    container_name: str
    protocol: str
    port: int
    ipv6_address: str
    interface_in: str
    interface_out: str

    def __str__(self):
        return f"{self.container_name}:{self.protocol}/{self.port} -> {self.ipv6_address}"


@dataclass
class ServiceRule:
    """Service防火墙和NAT规则"""
    service_id: str
    service_name: str
    container_id: str
    container_name: str
    protocol: str
    published_port: int  # 外部发布端口
    target_port: int     # 容器内部端口
    container_ipv6: str  # 容器IPv6地址
    interface_in: str    # 入接口
    interface_out: str   # 出接口

    def __str__(self):
        return f"{self.service_name}:{self.protocol}/{self.published_port}->{self.target_port} -> {self.container_ipv6}"


class FirewallManager:
    """IPv6防火墙管理器"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.active_rules: Dict[str, List[FirewallRule]] = {}
        self.active_service_rules: Dict[str, List[ServiceRule]] = {}  # Service规则
        self.ipv6_base_rules: List[List[str]] = []  # 记录IPv6基础规则
        
    def initialize(self):
        """初始化防火墙链"""
        self.logger.info("初始化防火墙链")

        # 确保所有专用链存在并被正确引用
        self._ensure_all_chains_exist()

        # 清空所有链中的规则（重要：确保干净的状态）
        self._flush_all_chains()

        # 设置基础规则
        self._ensure_base_rules()  # FORWARD链的DNAT conntrack规则
        self._setup_base_rules()   # INPUT链的IPv6基础协议和容器隔离规则

        # 清空内存中的规则记录
        self.active_rules.clear()
        self.active_service_rules.clear()
        self.logger.info("防火墙链初始化完成，已清空所有旧规则")
            
    def _ensure_chain_exists(self, iptables_cmd: str, chain_name: str):
        """确保链存在并被正确引用"""
        try:
            # 检查链是否存在
            result = subprocess.run([iptables_cmd, "-L", chain_name],
                                  capture_output=True, text=True)
            chain_exists = (result.returncode == 0)

            if not chain_exists:
                # 创建链
                subprocess.run([iptables_cmd, "-N", chain_name], check=True)
                self.logger.info(f"创建防火墙链: {chain_name}")

            # 检查FORWARD链中是否有对此链的引用
            forward_check = subprocess.run([iptables_cmd, "-C", "FORWARD", "-j", chain_name],
                                         capture_output=True, text=True)

            if forward_check.returncode != 0:
                # FORWARD链中没有引用，添加引用
                subprocess.run([iptables_cmd, "-I", "FORWARD", "1",
                              "-j", chain_name], check=True)
                self.logger.info(f"将链 {chain_name} 插入到FORWARD链")
            else:
                self.logger.debug(f"链 {chain_name} 已正确引用到FORWARD链")

        except subprocess.CalledProcessError as e:
            self.logger.error(f"确保防火墙链存在失败: {e}")
            raise

    def _ensure_all_chains_exist(self):
        """确保所有专用链存在并被正确引用"""
        # IPv6专用链
        # 1. FORWARD链 -> DOCKER_IPV6_FORWARD (容器和Service规则)
        self._ensure_chain_exists(self.config.ip6tables_cmd, self.config.chain_name)

        # 2. INPUT链 -> DOCKER_IPV6_INPUT (IPv6基础协议规则)
        self._ensure_input_chain_exists()

        # 3. PREROUTING链 -> DOCKER_IPV6_NAT (NAT规则)
        self._ensure_nat_chain_exists()

        # IPv4专用链
        # 4. FORWARD链 -> DOCKER_IPV4_FORWARD (IPv4容器规则)
        self._ensure_chain_exists(self.config.iptables_cmd, self.config.ipv4_chain_name)

        # 5. POSTROUTING链 -> DOCKER_IPV4_NAT (IPv4 NAT规则)
        self._ensure_ipv4_nat_chain_exists()

    def _ensure_input_chain_exists(self):
        """确保INPUT专用链存在并被正确引用"""
        try:
            # 检查链是否存在
            result = subprocess.run([self.config.ip6tables_cmd, "-L", self.config.input_chain_name],
                                  capture_output=True, text=True)
            if result.returncode != 0:
                # 创建链
                subprocess.run([self.config.ip6tables_cmd, "-N", self.config.input_chain_name], check=True)
                self.logger.info(f"创建IPv6基础协议链: {self.config.input_chain_name}")

            # 检查INPUT链中是否有对此链的引用
            input_check = subprocess.run([self.config.ip6tables_cmd, "-C", "INPUT", "-j", self.config.input_chain_name],
                                       capture_output=True, text=True)

            if input_check.returncode != 0:
                # INPUT链中没有引用，添加引用
                subprocess.run([self.config.ip6tables_cmd, "-I", "INPUT", "1",
                              "-j", self.config.input_chain_name], check=True)
                self.logger.info(f"将链 {self.config.input_chain_name} 插入到INPUT链")

        except subprocess.CalledProcessError as e:
            self.logger.error(f"确保INPUT专用链存在失败: {e}")
            raise

    def _ensure_nat_chain_exists(self):
        """确保NAT专用链存在并被正确引用"""
        try:
            # 检查链是否存在
            result = subprocess.run([self.config.ip6tables_cmd, "-t", "nat", "-L", self.config.nat_chain_name],
                                  capture_output=True, text=True)
            if result.returncode != 0:
                # 创建链
                subprocess.run([self.config.ip6tables_cmd, "-t", "nat", "-N", self.config.nat_chain_name], check=True)
                self.logger.info(f"创建NAT专用链: {self.config.nat_chain_name}")

            # 检查PREROUTING链中是否有对此链的引用
            prerouting_check = subprocess.run([self.config.ip6tables_cmd, "-t", "nat", "-C", "PREROUTING", "-j", self.config.nat_chain_name],
                                            capture_output=True, text=True)

            if prerouting_check.returncode != 0:
                # PREROUTING链中没有引用，添加引用
                subprocess.run([self.config.ip6tables_cmd, "-t", "nat", "-I", "PREROUTING", "1",
                              "-j", self.config.nat_chain_name], check=True)
                self.logger.info(f"将链 {self.config.nat_chain_name} 插入到PREROUTING链")

        except subprocess.CalledProcessError as e:
            self.logger.error(f"确保NAT专用链存在失败: {e}")
            raise

    def _ensure_ipv4_nat_chain_exists(self):
        """确保IPv4 NAT专用链存在并被正确引用"""
        try:
            # 检查链是否存在
            result = subprocess.run([self.config.iptables_cmd, "-t", "nat", "-L", self.config.ipv4_nat_chain_name],
                                  capture_output=True, text=True)
            if result.returncode != 0:
                # 创建链
                subprocess.run([self.config.iptables_cmd, "-t", "nat", "-N", self.config.ipv4_nat_chain_name], check=True)
                self.logger.info(f"创建IPv4 NAT专用链: {self.config.ipv4_nat_chain_name}")

            # 检查POSTROUTING链中是否有对此链的引用
            postrouting_check = subprocess.run([self.config.iptables_cmd, "-t", "nat", "-C", "POSTROUTING", "-j", self.config.ipv4_nat_chain_name],
                                            capture_output=True, text=True)

            if postrouting_check.returncode != 0:
                # POSTROUTING链中没有引用，添加引用
                subprocess.run([self.config.iptables_cmd, "-t", "nat", "-I", "POSTROUTING", "1",
                              "-j", self.config.ipv4_nat_chain_name], check=True)
                self.logger.info(f"将链 {self.config.ipv4_nat_chain_name} 插入到POSTROUTING链")

        except subprocess.CalledProcessError as e:
            self.logger.error(f"确保IPv4 NAT专用链存在失败: {e}")
            raise

    def _ensure_base_rules(self):
        """确保基础规则存在"""
        try:
            # IPv6 DNAT conntrack规则 - 允许所有经过NAT转换的连接
            dnat_rule_check = subprocess.run([
                self.config.ip6tables_cmd, "-C", self.config.chain_name,
                "-i", self.config.parent_interface,
                "-o", self.config.gateway_macvlan,
                "-m", "conntrack", "--ctstate", "DNAT",
                "-j", "ACCEPT"
            ], capture_output=True, text=True)

            if dnat_rule_check.returncode != 0:
                # 添加DNAT conntrack规则
                subprocess.run([
                    self.config.ip6tables_cmd, "-I", self.config.chain_name, "1",
                    "-i", self.config.parent_interface,
                    "-o", self.config.gateway_macvlan,
                    "-m", "conntrack", "--ctstate", "DNAT",
                    "-j", "ACCEPT"
                ], check=True)
                self.logger.info("添加IPv6 DNAT conntrack基础规则")
            else:
                self.logger.debug("IPv6 DNAT conntrack基础规则已存在")

        except subprocess.CalledProcessError as e:
            self.logger.error(f"确保基础规则失败: {e}")
            raise

    def _ensure_container_isolation_rules(self):
        """
                    确保容器隔离规则存在。
                    改动：
        1. 添加 DOCKER_IPV6FW_ISO 隔离链接，用于禁止子网访问主机接口
        2. DOCKER_IPV6FW_ISO 隔离链可以手动添加豁免规则，不会被IPV6FW清除，可添加 netbird 的dns服务等
           如: 
             iptables -I DOCKER_IPV6FW_ISO -i macvlan_gw -p udp -m addrtype --dst-type LOCAL -m udp --dport 53 -j ACCEPT

             ip6tables -I DOCKER_IPV6FW_ISO -i macvlan_gw -p udp -m addrtype --dst-type LOCAL -m udp --dport 53 -j ACCEPT
        """

        iso_chain = "DOCKER_IPV6FW_ISO"

        try:
            # ======================= IPv4 处理 =======================
            # 1. 尝试创建自定义链 (如果存在会报错，忽略即可)
            subprocess.run([self.config.iptables_cmd, "-N", iso_chain], 
                           check=False, capture_output=True)

            # 2. 确保 INPUT 链跳转到自定义链 
            # 规则：-j DOCKER_IPV6FW_ISO
            ipv4_jump_check = subprocess.run([
                self.config.iptables_cmd, "-C", "INPUT",
                "-j", iso_chain
            ], capture_output=True, text=True)

            if ipv4_jump_check.returncode != 0:
                # 插入到第1位，确保优先执行
                subprocess.run([
                    self.config.iptables_cmd, "-I", "INPUT", "1",
                    "-j", iso_chain
                ], check=True)
                self.logger.info(f"添加IPv4隔离链跳转: INPUT -> {iso_chain} (无网卡限制)")

            # 3. 确保自定义链尾部存在“兜底”隔离规则
            # 规则：-i <macvlan> ! -p icmp -m addrtype --dst-type LOCAL -j DROP
            ipv4_drop_check = subprocess.run([
                self.config.iptables_cmd, "-C", iso_chain,
                "-i", self.config.gateway_macvlan,
                "!", "-p", "icmp",
                "-m", "addrtype", "--dst-type", "LOCAL",
                "-j", "DROP"
            ], capture_output=True, text=True)

            if ipv4_drop_check.returncode != 0:
                subprocess.run([
                    self.config.iptables_cmd, "-A", iso_chain,
                    "-i", self.config.gateway_macvlan,
                    "!", "-p", "icmp",
                    "-m", "addrtype", "--dst-type", "LOCAL",
                    "-j", "DROP"
                ], check=True)
                self.logger.info(f"在 {iso_chain} 尾部添加IPv4默认隔离规则 (限制来源: {self.config.gateway_macvlan})")
            else:
                self.logger.debug(f"IPv4默认隔离规则已存在于 {iso_chain}")

            # ======================= IPv6 处理 =======================
            # 1. 尝试创建自定义链
            subprocess.run([self.config.ip6tables_cmd, "-N", iso_chain], 
                           check=False, capture_output=True)

            # 2. 确保在INPUT链第一行插入链跳转 
            ipv6_jump_check = subprocess.run([
                self.config.ip6tables_cmd, "-C", "INPUT",
                "-j", iso_chain
            ], capture_output=True, text=True)

            if ipv6_jump_check.returncode != 0:
                subprocess.run([
                    self.config.ip6tables_cmd, "-I", "INPUT", "1",
                    "-j", iso_chain
                ], check=True)
                self.logger.info(f"添加IPv6隔离链跳转: INPUT -> {iso_chain} (无网卡限制)")

            # 3. 确保自定义链尾部存在“兜底”隔离规则
            # 关键改动：在这里限制 -i gateway_macvlan
            ipv6_drop_check = subprocess.run([
                self.config.ip6tables_cmd, "-C", iso_chain,
                "-i", self.config.gateway_macvlan,
                "!", "-p", "ipv6-icmp",
                "-m", "addrtype", "--dst-type", "LOCAL",
                "-j", "DROP"
            ], capture_output=True, text=True)

            if ipv6_drop_check.returncode != 0:
                subprocess.run([
                    self.config.ip6tables_cmd, "-A", iso_chain,
                    "-i", self.config.gateway_macvlan,
                    "!", "-p", "ipv6-icmp",
                    "-m", "addrtype", "--dst-type", "LOCAL",
                    "-j", "DROP"
                ], check=True)
                self.logger.info(f"在 {iso_chain} 尾部添加IPv6默认隔离规则 (限制来源: {self.config.gateway_macvlan})")
            else:
                self.logger.debug(f"IPv6默认隔离规则已存在于 {iso_chain}")

        except subprocess.CalledProcessError as e:
            self.logger.error(f"确保容器隔离规则失败: {e}")
            raise

    def _cleanup_container_isolation_rules(self):
        """
        清理容器隔离规则。
        逻辑：仅删除 INPUT 链中对自定义链的引用，保留自定义链本身以保存用户豁免规则。
        """
        iso_chain = "DOCKER_IPV6FW_ISO"

        try:
            # 清理 IPv4 INPUT 跳转规则 (注意：查找时不带 -i 参数)
            subprocess.run([
                self.config.iptables_cmd, "-D", "INPUT",
                "-j", iso_chain
            ], check=False, capture_output=True)
            self.logger.debug(f"移除 IPv4 INPUT 链对 {iso_chain} 的引用")

            # 清理 IPv6 INPUT 跳转规则
            subprocess.run([
                self.config.ip6tables_cmd, "-D", "INPUT",
                "-j", iso_chain
            ], check=False, capture_output=True)
            self.logger.debug(f"移除 IPv6 INPUT 链对 {iso_chain} 的引用")
            
            # 不删除链本身，保留用户自定义规则

        except Exception as e:
            self.logger.warning(f"清理容器隔离规则时出错: {e}")

    def _flush_chain(self):
        """清空主FORWARD链中的所有规则"""
        try:
            # 清空链中的所有规则
            result = subprocess.run([self.config.ip6tables_cmd, "-F", self.config.chain_name], capture_output=True, text=True)
            if result.returncode == 0:
                self.logger.info(f"已清空防火墙链 {self.config.chain_name} 中的所有规则")
            else:
                self.logger.warning(f"清空防火墙链失败: {result.stderr}")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"清空防火墙链失败: {e}")

    def _flush_all_chains(self):
        """清空所有专用链中的规则"""
        # 清空IPv6 FORWARD专用链
        self._flush_chain()

        # 清空IPv6 INPUT专用链
        try:
            result = subprocess.run([self.config.ip6tables_cmd, "-F", self.config.input_chain_name],
                                  capture_output=True, text=True)
            if result.returncode == 0:
                self.logger.info(f"已清空IPv6基础协议链 {self.config.input_chain_name}")
        except subprocess.CalledProcessError as e:
            self.logger.warning(f"清空IPv6基础协议链失败: {e}")

        # 清空IPv6 NAT专用链
        try:
            result = subprocess.run([self.config.ip6tables_cmd, "-t", "nat", "-F", self.config.nat_chain_name],
                                  capture_output=True, text=True)
            if result.returncode == 0:
                self.logger.info(f"已清空IPv6 NAT专用链 {self.config.nat_chain_name}")
        except subprocess.CalledProcessError as e:
            self.logger.warning(f"清空IPv6 NAT专用链失败: {e}")

        # 清空IPv4 FORWARD专用链
        try:
            result = subprocess.run([self.config.iptables_cmd, "-F", self.config.ipv4_chain_name],
                                  capture_output=True, text=True)
            if result.returncode == 0:
                self.logger.info(f"已清空IPv4 FORWARD专用链 {self.config.ipv4_chain_name}")
        except subprocess.CalledProcessError as e:
            self.logger.warning(f"清空IPv4 FORWARD专用链失败: {e}")

        # 清空IPv4 NAT专用链
        try:
            result = subprocess.run([self.config.iptables_cmd, "-t", "nat", "-F", self.config.ipv4_nat_chain_name],
                                  capture_output=True, text=True)
            if result.returncode == 0:
                self.logger.info(f"已清空IPv4 NAT专用链 {self.config.ipv4_nat_chain_name}")
        except subprocess.CalledProcessError as e:
            self.logger.warning(f"清空IPv4 NAT专用链失败: {e}")

        # 清理容器隔离规则
        self._cleanup_container_isolation_rules()

    def _remove_chain_completely(self):
        """完全删除防火墙链（用于彻底清理）"""
        try:
            chain_name = self.config.chain_name

            # 检查链是否存在
            check_result = subprocess.run(["ip6tables", "-L", chain_name],
                                        capture_output=True, text=True)

            if check_result.returncode != 0:
                self.logger.debug(f"防火墙链 {chain_name} 不存在，无需删除")
                return

            # 检查FORWARD链中是否有对我们链的引用
            forward_check = subprocess.run(["ip6tables", "-C", "FORWARD", "-j", chain_name],
                                         capture_output=True, text=True)

            if forward_check.returncode == 0:
                # 从FORWARD链中删除对我们链的引用
                result = subprocess.run(["ip6tables", "-D", "FORWARD", "-j", chain_name],
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    self.logger.info(f"已从FORWARD链中删除对 {chain_name} 的引用")
                else:
                    self.logger.warning(f"删除FORWARD链引用失败: {result.stderr}")

            # 清空链
            result = subprocess.run(["ip6tables", "-F", chain_name],
                                  capture_output=True, text=True)
            if result.returncode == 0:
                self.logger.info(f"已清空防火墙链 {chain_name}")

            # 删除链
            result = subprocess.run(["ip6tables", "-X", chain_name],
                                  capture_output=True, text=True)

            if result.returncode == 0:
                self.logger.info(f"已完全删除防火墙链 {chain_name}")
            else:
                self.logger.warning(f"删除防火墙链失败: {result.stderr}")

        except subprocess.CalledProcessError as e:
            self.logger.error(f"删除防火墙链异常: {e}")

    def _cleanup_ipv6_base_rules(self):
        """清理IPv6基础规则 - 只删除我们添加的规则"""
        if not hasattr(self, 'ipv6_base_rules') or not self.ipv6_base_rules:
            self.logger.debug("没有记录的IPv6基础规则需要清理")
            return

        self.logger.info("清理IPv6基础规则（只删除我们添加的规则）")

        for rule in self.ipv6_base_rules:
            try:
                # 将-A替换为-D来删除规则
                delete_rule = [r.replace("-A", "-D") if r == "-A" else r for r in rule]

                # 先检查规则是否存在，避免重复删除
                check_rule = [r.replace("-A", "-C") if r == "-A" else r for r in rule]
                check_result = subprocess.run(["ip6tables"] + check_rule,
                                            capture_output=True, text=True)

                if check_result.returncode == 0:
                    # 规则存在，尝试删除
                    result = subprocess.run(["ip6tables"] + delete_rule,
                                          capture_output=True, text=True)
                    if result.returncode == 0:
                        self.logger.info(f"删除IPv6基础规则: {' '.join(delete_rule[2:])}")
                    else:
                        self.logger.warning(f"删除IPv6基础规则失败: {result.stderr.strip()}")
                else:
                    self.logger.debug(f"IPv6基础规则不存在（可能已被删除）: {' '.join(delete_rule[2:])}")

            except subprocess.CalledProcessError as e:
                self.logger.warning(f"检查/删除IPv6基础规则异常: {e}")

        # 清空记录，避免重复删除
        self.ipv6_base_rules.clear()
        self.logger.debug("IPv6基础规则记录已清空")
            
    def _setup_base_rules(self):
        """设置基础规则"""
        # 注意：不再添加宽泛的转发规则，只添加IPv6基础协议支持
        self.logger.info("设置IPv6基础协议支持规则")

        # IPv6基础协议规则（专用INPUT链）
        icmpv6_rules = [
            # ICMPv6基础消息类型
            ["-A", self.config.input_chain_name, "-p", "icmpv6", "--icmpv6-type", "destination-unreachable", "-j", "ACCEPT"],
            ["-A", self.config.input_chain_name, "-p", "icmpv6", "--icmpv6-type", "packet-too-big", "-j", "ACCEPT"],
            ["-A", self.config.input_chain_name, "-p", "icmpv6", "--icmpv6-type", "time-exceeded", "-j", "ACCEPT"],
            ["-A", self.config.input_chain_name, "-p", "icmpv6", "--icmpv6-type", "parameter-problem", "-j", "ACCEPT"],
            # NDP (Neighbor Discovery Protocol)
            ["-A", self.config.input_chain_name, "-p", "icmpv6", "--icmpv6-type", "neighbor-solicitation", "-j", "ACCEPT"],
            ["-A", self.config.input_chain_name, "-p", "icmpv6", "--icmpv6-type", "neighbor-advertisement", "-j", "ACCEPT"],
            ["-A", self.config.input_chain_name, "-p", "icmpv6", "--icmpv6-type", "router-advertisement", "-j", "ACCEPT"],
            ["-A", self.config.input_chain_name, "-p", "icmpv6", "--icmpv6-type", "router-solicitation", "-j", "ACCEPT"],
            # 链路本地地址
            ["-A", self.config.input_chain_name, "-s", self.config.ipv6_link_local, "-j", "ACCEPT"],
            ["-A", self.config.input_chain_name, "-d", self.config.ipv6_link_local, "-j", "ACCEPT"]
        ]

        # 记录添加的IPv6基础规则（用于清理）
        self.ipv6_base_rules = []

        for rule in icmpv6_rules:
            try:
                if not self._rule_exists("ip6tables", rule):
                    subprocess.run(["ip6tables"] + rule, check=True)
                    self.logger.info(f"添加IPv6基础规则: {' '.join(rule[2:])}")  # 跳过-A INPUT
                    # 只记录我们真正添加的规则
                    self.ipv6_base_rules.append(rule)
                else:
                    self.logger.debug(f"IPv6基础规则已存在（系统原有）: {' '.join(rule[2:])}")
                    # 不记录已存在的规则，避免误删系统原有规则
            except subprocess.CalledProcessError as e:
                self.logger.error(f"添加IPv6基础规则失败: {e}")

        self.logger.info("IPv6基础协议支持规则设置完成")

        # 添加容器隔离规则（必须在最后，确保优先级最高）
        self._ensure_container_isolation_rules()

        # 添加ICMPv6/NDP协议的FORWARD规则（接口间转发）
        self._setup_icmpv6_forward_rules()

    def _setup_icmpv6_forward_rules(self):
        """设置ICMP/ICMPv6协议的FORWARD规则 - 确保接口间协议转发正常"""
        self.logger.info("设置ICMP/ICMPv6协议FORWARD规则")

        # ICMPv6/NDP协议双向转发规则（专用FORWARD链）
        icmpv6_forward_rules = [
            # 主接口到macvlan网关的ICMPv6转发
            ["-A", self.config.chain_name, "-i", self.config.parent_interface,
             "-o", self.config.gateway_macvlan, "-p", "icmpv6", "-j", "ACCEPT"],
            # macvlan网关到主接口的ICMPv6转发
            ["-A", self.config.chain_name, "-i", self.config.gateway_macvlan,
             "-o", self.config.parent_interface, "-p", "icmpv6", "-j", "ACCEPT"]
        ]

        # ICMPv4协议双向转发规则（使用IPv4专用链）
        icmpv4_forward_rules = [
            # 主接口到macvlan网关的ICMPv4转发
            ["-A", self.config.ipv4_chain_name, "-i", self.config.parent_interface,
             "-o", self.config.gateway_macvlan, "-p", "icmp", "-j", "ACCEPT"],
            # macvlan网关到主接口的ICMPv4转发
            ["-A", self.config.ipv4_chain_name, "-i", self.config.gateway_macvlan,
             "-o", self.config.parent_interface, "-p", "icmp", "-j", "ACCEPT"]
        ]

        # 添加ICMPv6规则
        for rule in icmpv6_forward_rules:
            try:
                if not self._rule_exists(self.config.ip6tables_cmd, rule):
                    subprocess.run([self.config.ip6tables_cmd] + rule, check=True)
                    self.logger.info(f"添加ICMPv6 FORWARD规则: {rule[2]} -> {rule[4]}")
                else:
                    self.logger.debug(f"ICMPv6 FORWARD规则已存在: {rule[2]} -> {rule[4]}")
            except subprocess.CalledProcessError as e:
                self.logger.error(f"添加ICMPv6 FORWARD规则失败: {e}")

        # 添加ICMPv4规则（使用iptables）
        for rule in icmpv4_forward_rules:
            try:
                if not self._rule_exists(self.config.iptables_cmd, rule):
                    subprocess.run([self.config.iptables_cmd] + rule, check=True)
                    self.logger.info(f"添加ICMPv4 FORWARD规则: {rule[2]} -> {rule[4]}")
                else:
                    self.logger.debug(f"ICMPv4 FORWARD规则已存在: {rule[2]} -> {rule[4]}")
            except subprocess.CalledProcessError as e:
                self.logger.error(f"添加ICMPv4 FORWARD规则失败: {e}")

        self.logger.info("ICMP/ICMPv6协议FORWARD规则设置完成")

        # 设置IPv4容器上网的完整规则
        self._setup_ipv4_container_internet_rules()

    def _setup_ipv4_container_internet_rules(self):
        """设置IPv4容器上网的完整规则 - 确保IPv4容器能正常访问外网"""
        self.logger.info("设置IPv4容器上网规则")

        # IPv4容器上网的FORWARD规则
        ipv4_forward_rules = [
            # 1. 容器到外网的FORWARD规则（gateway_macvlan -> parent_interface）
            ["-A", self.config.ipv4_chain_name, "-i", self.config.gateway_macvlan,
             "-o", self.config.parent_interface, "-j", "ACCEPT"]
        ]

        # IPv4 NAT MASQUERADE规则（POSTROUTING链）
        ipv4_nat_rules = [
            # 4. NAT MASQUERADE规则 - 容器访问外网时进行地址伪装
            ["-t", "nat", "-A", self.config.ipv4_nat_chain_name,
             "-o", self.config.parent_interface, "-j", "MASQUERADE"]
        ]

        # 添加IPv4 FORWARD规则
        for rule in ipv4_forward_rules:
            try:
                if not self._rule_exists(self.config.iptables_cmd, rule):
                    subprocess.run([self.config.iptables_cmd] + rule, check=True)
                    self.logger.info(f"添加IPv4 FORWARD规则: {rule[2]} -> {rule[4]}")
                else:
                    self.logger.debug(f"IPv4 FORWARD规则已存在: {rule[2]} -> {rule[4]}")
            except subprocess.CalledProcessError as e:
                self.logger.error(f"添加IPv4 FORWARD规则失败: {e}")

        # 添加IPv4 NAT规则
        for rule in ipv4_nat_rules:
            try:
                if not self._rule_exists(self.config.iptables_cmd, rule):
                    subprocess.run([self.config.iptables_cmd] + rule, check=True)
                    self.logger.info(f"添加IPv4 NAT MASQUERADE规则: {rule[4]} -> {rule[6]}")
                else:
                    self.logger.debug(f"IPv4 NAT MASQUERADE规则已存在: {rule[4]} -> {rule[6]}")
            except subprocess.CalledProcessError as e:
                self.logger.error(f"添加IPv4 NAT MASQUERADE规则失败: {e}")

        self.logger.info("IPv4容器上网规则设置完成")

    def _rule_exists(self, iptables_cmd: str, rule: List[str]) -> bool:
        """检查规则是否存在"""
        try:
            # 将-A替换为-C来检查规则
            check_rule = [r.replace("-A", "-C") if r == "-A" else r for r in rule]
            result = subprocess.run([iptables_cmd] + check_rule, 
                                  capture_output=True, text=True)
            return result.returncode == 0
        except subprocess.CalledProcessError:
            return False
            
    def add_container_rules(self, container_id: str, container_name: str, 
                          port_mappings: List[Dict], networks: Dict):
        """为容器添加防火墙规则"""
        if container_id in self.active_rules:
            self.logger.debug(f"容器 {container_name} 的规则已存在")
            return
            
        rules = []
        
        # 处理每个网络接口
        for network_name, network_info in networks.items():
            if not self._should_monitor_network(network_name):
                continue
                
            ipv6_address = network_info.get('GlobalIPv6Address')
            if not ipv6_address:
                continue
                
            # 处理端口映射
            for port_info in port_mappings:
                protocol = port_info.get('protocol', 'tcp')
                port = port_info.get('port')

                if port:
                    # 处理all协议（创建tcp和udp两条规则）
                    protocols_to_process = ['tcp', 'udp'] if protocol == 'all' else [protocol]

                    for actual_protocol in protocols_to_process:
                        rule = FirewallRule(
                            container_id=container_id,
                            container_name=container_name,
                            protocol=actual_protocol,
                            port=port,
                            ipv6_address=ipv6_address,
                            interface_in=self.config.parent_interface,
                            interface_out=self.config.gateway_macvlan
                        )

                        if self._add_firewall_rule(rule):
                            rules.append(rule)
                        
        if rules:
            self.active_rules[container_id] = rules
            self.logger.info(f"为容器 {container_name} 添加了 {len(rules)} 条规则")
            
    def _should_monitor_network(self, network_name: str) -> bool:
        """判断是否应该监控此网络"""
        for monitored in self.config.monitored_networks:
            if monitored.lower() in network_name.lower():
                return True
        return False
        
    def _add_firewall_rule(self, rule: FirewallRule) -> bool:
        """添加单条防火墙规则"""
        try:
            # 构建ip6tables规则 - 只允许特定容器的特定端口
            iptables_rule = [
                "-A", self.config.chain_name,
                "-p", rule.protocol,
                "-d", rule.ipv6_address,  # 目标是特定容器的IPv6地址
                "--dport", str(rule.port),  # 特定端口
                "-i", rule.interface_in,   # 从外网接口进入
                "-o", rule.interface_out,  # 到macvlan接口
                "-j", "ACCEPT"
            ]

            # 检查规则是否已存在
            if self._rule_exists("ip6tables", iptables_rule):
                self.logger.debug(f"规则已存在: {rule}")
                return True

            # 添加规则
            subprocess.run(["ip6tables"] + iptables_rule, check=True)
            self.logger.info(f"添加容器防火墙规则: {rule}")
            return True

        except subprocess.CalledProcessError as e:
            self.logger.error(f"添加防火墙规则失败: {rule}, 错误: {e}")
            return False
            
    def remove_container_rules(self, container_id: str):
        """移除容器的防火墙规则"""
        if container_id not in self.active_rules:
            return
            
        rules = self.active_rules[container_id]
        removed_count = 0
        
        for rule in rules:
            if self._remove_firewall_rule(rule):
                removed_count += 1
                
        del self.active_rules[container_id]
        self.logger.info(f"移除容器 {rules[0].container_name} 的 {removed_count} 条规则")

    def add_container_public_rules(self, container_id: str, container_name: str,
                                  public_ports: List[Dict], networks: Dict):
        """为容器的Public端口添加NAT和防火墙规则"""
        # 使用特殊的ID来区分Public端口规则
        public_rule_id = f"{container_id}_public"

        # 检查是否需要更新规则
        if public_rule_id in self.active_service_rules:
            # 比较现有规则与新配置，如果有变化则先移除旧规则
            if self._container_public_rules_changed(public_rule_id, public_ports, networks):
                self.logger.info(f"检测到容器 {container_name} Public端口配置变化，更新规则")
                self.remove_service_rules(public_rule_id)
            else:
                self.logger.debug(f"容器 {container_name} Public端口规则无变化，跳过")
                return

        rules = []

        # 处理每个网络接口
        for network_name, network_info in networks.items():
            if not self._should_monitor_network(network_name):
                continue

            ipv6_address = network_info.get('GlobalIPv6Address')
            if not ipv6_address:
                continue

            # 处理Public端口映射
            for port_info in public_ports:
                protocol = port_info.get('protocol', 'tcp')
                container_port = port_info.get('container_port')
                host_port = port_info.get('host_port')
                host_ip = port_info.get('host_ip', '')

                if container_port and host_port:
                    # 处理all协议（创建tcp和udp两条规则）
                    protocols_to_process = ['tcp', 'udp'] if protocol == 'all' else [protocol]

                    for actual_protocol in protocols_to_process:
                        # 只为端口不同的映射创建NAT规则
                        if host_port != container_port:
                            # 创建NAT + FORWARD规则（类似Service规则）
                            rule = ServiceRule(
                                service_id=public_rule_id,
                                service_name=f"{container_name}_public",
                                container_id=container_id,
                                container_name=container_name,
                                protocol=actual_protocol,
                                published_port=host_port,
                                target_port=container_port,
                                container_ipv6=ipv6_address,
                                interface_in=self.config.parent_interface,
                                interface_out=self.config.gateway_macvlan
                            )

                            if self._add_service_rule(rule):
                                rules.append(rule)
                                self.logger.debug(f"  创建NAT规则: {host_port}->{container_port}/{actual_protocol} (端口不同)")
                        else:
                            # 端口相同，只需要FORWARD规则，无需NAT转换
                            self.logger.debug(f"  跳过NAT规则: {host_port}->{container_port}/{actual_protocol} (端口相同，IPv6可直接访问)")

                            # 创建FORWARD规则
                            forward_rule = FirewallRule(
                                container_id=container_id,
                                container_name=container_name,
                                protocol=actual_protocol,
                                port=container_port,
                                ipv6_address=ipv6_address,
                                interface_in=self.config.parent_interface,
                                interface_out=self.config.gateway_macvlan
                            )

                            # 检查是否已经有相同的FORWARD规则
                            if container_id in self.active_rules:
                                existing_rules = self.active_rules[container_id]
                                rule_exists = any(
                                    r.protocol == actual_protocol and r.port == container_port and r.ipv6_address == ipv6_address
                                    for r in existing_rules
                                )
                                if not rule_exists and self._add_firewall_rule(forward_rule):
                                    existing_rules.append(forward_rule)
                                    self.logger.debug(f"  添加FORWARD规则: {container_port}/{actual_protocol} (端口相同)")
                            else:
                                if self._add_firewall_rule(forward_rule):
                                    self.active_rules[container_id] = [forward_rule]
                                    self.logger.debug(f"  添加FORWARD规则: {container_port}/{actual_protocol} (端口相同)")

        if rules:
            self.active_service_rules[public_rule_id] = rules
            self.logger.info(f"为容器 {container_name} 添加了 {len(rules)} 条Public端口规则")

            # 记录详细的规则信息便于调试
            for rule in rules:
                self.logger.debug(f"  容器Public规则: {rule.protocol}:{rule.published_port}->{rule.target_port} -> {rule.container_ipv6}")
        else:
            self.logger.debug(f"容器 {container_name} 没有生成有效Public端口规则")

    def _container_public_rules_changed(self, public_rule_id: str, new_public_ports: List[Dict],
                                       new_networks: Dict) -> bool:
        """检测容器Public端口规则是否发生变化"""
        if public_rule_id not in self.active_service_rules:
            return True  # 没有现有规则，需要添加

        existing_rules = self.active_service_rules[public_rule_id]

        # 构建新规则的特征集合用于比较
        new_rule_signatures = set()
        for network_name, network_info in new_networks.items():
            if not self._should_monitor_network(network_name):
                continue

            ipv6_address = network_info.get('GlobalIPv6Address')
            if not ipv6_address:
                continue

            for port_info in new_public_ports:
                protocol = port_info.get('protocol', 'tcp')
                container_port = port_info.get('container_port')
                host_port = port_info.get('host_port')

                if container_port and host_port:
                    # 处理all协议（创建tcp和udp两个特征）
                    protocols_to_check = ['tcp', 'udp'] if protocol == 'all' else [protocol]

                    for actual_protocol in protocols_to_check:
                        # 只为端口不同的映射创建NAT规则特征
                        if host_port != container_port:
                            # 创建规则特征：协议_宿主机端口_容器端口_IPv6地址
                            signature = f"{actual_protocol}_{host_port}_{container_port}_{ipv6_address}"
                            new_rule_signatures.add(signature)

        # 构建现有规则的特征集合
        existing_rule_signatures = set()
        for rule in existing_rules:
            signature = f"{rule.protocol}_{rule.published_port}_{rule.target_port}_{rule.container_ipv6}"
            existing_rule_signatures.add(signature)

        # 比较两个集合是否相同
        rules_changed = new_rule_signatures != existing_rule_signatures

        if rules_changed:
            self.logger.info(f"容器Public端口 {public_rule_id} 规则变化检测:")
            self.logger.info(f"  现有规则: {existing_rule_signatures}")
            self.logger.info(f"  新规则: {new_rule_signatures}")

        return rules_changed

    def add_custom_firewall_rules(self, container_id: str, container_name: str,
                                 custom_ports: List[Dict], networks: Dict):
        """为容器的自定义防火墙端口添加规则"""
        # 使用特殊的ID来区分自定义防火墙规则
        custom_rule_id = f"{container_id}_custom"

        # 检查是否需要更新规则
        if custom_rule_id in self.active_service_rules:
            # 比较现有规则与新配置，如果有变化则先移除旧规则
            if self._custom_firewall_rules_changed(custom_rule_id, custom_ports, networks):
                self.logger.info(f"检测到容器 {container_name} 自定义防火墙配置变化，更新规则")
                self.remove_service_rules(custom_rule_id)
            else:
                self.logger.debug(f"容器 {container_name} 自定义防火墙规则无变化，跳过")
                return

        rules = []

        # 处理每个网络接口
        for network_name, network_info in networks.items():
            if not self._should_monitor_network(network_name):
                continue

            ipv6_address = network_info.get('GlobalIPv6Address')
            if not ipv6_address:
                continue

            # 处理自定义防火墙端口
            for port_info in custom_ports:
                protocol = port_info.get('protocol', 'tcp')
                external_port = port_info.get('external_port')
                internal_port = port_info.get('internal_port')

                if external_port and internal_port:
                    # 处理all协议（创建tcp和udp两条规则）
                    protocols_to_process = ['tcp', 'udp'] if protocol == 'all' else [protocol]

                    for actual_protocol in protocols_to_process:
                        if external_port != internal_port:
                            # 需要NAT规则（端口不同）
                            rule = ServiceRule(
                                service_id=custom_rule_id,
                                service_name=f"{container_name}_custom",
                                container_id=container_id,
                                container_name=container_name,
                                protocol=actual_protocol,
                                published_port=external_port,
                                target_port=internal_port,
                                container_ipv6=ipv6_address,
                                interface_in=self.config.parent_interface,
                                interface_out=self.config.gateway_macvlan
                            )

                            if self._add_service_rule(rule):
                                rules.append(rule)
                                self.logger.debug(f"  自定义NAT规则: {external_port}->{internal_port}/{actual_protocol}")
                        else:
                            # 端口相同，只需要FORWARD规则
                            forward_rule = FirewallRule(
                                container_id=container_id,
                                container_name=container_name,
                                protocol=actual_protocol,
                                port=external_port,
                                ipv6_address=ipv6_address,
                                interface_in=self.config.parent_interface,
                                interface_out=self.config.gateway_macvlan
                            )

                            if self._add_firewall_rule(forward_rule):
                                # 将FORWARD规则也加入到service_rules中统一管理
                                service_rule = ServiceRule(
                                    service_id=custom_rule_id,
                                    service_name=f"{container_name}_custom",
                                    container_id=container_id,
                                    container_name=container_name,
                                    protocol=actual_protocol,
                                    published_port=external_port,
                                    target_port=internal_port,
                                    container_ipv6=ipv6_address,
                                    interface_in=self.config.parent_interface,
                                    interface_out=self.config.gateway_macvlan
                                )
                                rules.append(service_rule)
                                self.logger.debug(f"  自定义FORWARD规则: {external_port}/{actual_protocol}")

        if rules:
            self.active_service_rules[custom_rule_id] = rules
            self.logger.info(f"为容器 {container_name} 添加了 {len(rules)} 条自定义防火墙规则")

            # 记录详细的规则信息便于调试
            for rule in rules:
                self.logger.debug(f"  自定义规则: {rule.protocol}:{rule.published_port}->{rule.target_port} -> {rule.container_ipv6}")
        else:
            self.logger.debug(f"容器 {container_name} 没有生成有效自定义防火墙规则")

    def _custom_firewall_rules_changed(self, custom_rule_id: str, new_custom_ports: List[Dict],
                                      new_networks: Dict) -> bool:
        """检测自定义防火墙规则是否发生变化"""
        if custom_rule_id not in self.active_service_rules:
            return True  # 没有现有规则，需要添加

        existing_rules = self.active_service_rules[custom_rule_id]

        # 构建新规则的特征集合用于比较
        new_rule_signatures = set()
        for network_name, network_info in new_networks.items():
            if not self._should_monitor_network(network_name):
                continue

            ipv6_address = network_info.get('GlobalIPv6Address')
            if not ipv6_address:
                continue

            for port_info in new_custom_ports:
                protocol = port_info.get('protocol', 'tcp')
                external_port = port_info.get('external_port')
                internal_port = port_info.get('internal_port')

                if external_port and internal_port:
                    # 处理all协议（创建tcp和udp两个特征）
                    protocols_to_check = ['tcp', 'udp'] if protocol == 'all' else [protocol]

                    for actual_protocol in protocols_to_check:
                        # 创建规则特征：协议_外部端口_内部端口_IPv6地址
                        signature = f"{actual_protocol}_{external_port}_{internal_port}_{ipv6_address}"
                        new_rule_signatures.add(signature)

        # 构建现有规则的特征集合
        existing_rule_signatures = set()
        for rule in existing_rules:
            signature = f"{rule.protocol}_{rule.published_port}_{rule.target_port}_{rule.container_ipv6}"
            existing_rule_signatures.add(signature)

        # 比较两个集合是否相同
        rules_changed = new_rule_signatures != existing_rule_signatures

        if rules_changed:
            self.logger.info(f"自定义防火墙规则 {custom_rule_id} 变化检测:")
            self.logger.info(f"  现有规则: {existing_rule_signatures}")
            self.logger.info(f"  新规则: {new_rule_signatures}")

        return rules_changed

    def _remove_firewall_rule(self, rule: FirewallRule) -> bool:
        """移除单条防火墙规则"""
        try:
            # 构建ip6tables规则（先检查是否存在）
            check_rule = [
                "-C", self.config.chain_name,
                "-p", rule.protocol,
                "-d", rule.ipv6_address,
                "--dport", str(rule.port),
                "-i", rule.interface_in,
                "-o", rule.interface_out,
                "-j", "ACCEPT"
            ]

            # 先检查规则是否存在
            check_result = subprocess.run(["ip6tables"] + check_rule,
                                        capture_output=True, text=True)

            if check_result.returncode == 0:
                # 规则存在，执行删除
                delete_rule = [r.replace("-C", "-D") if r == "-C" else r for r in check_rule]
                subprocess.run(["ip6tables"] + delete_rule, check=True)
                self.logger.info(f"移除防火墙规则: {rule}")
                return True
            else:
                self.logger.debug(f"防火墙规则不存在（可能已被删除）: {rule}")
                return True  # 规则不存在也算成功

        except subprocess.CalledProcessError as e:
            self.logger.warning(f"移除防火墙规则失败: {rule}, 错误: {e}")
            return False
            
    def cleanup(self):
        """清理所有规则"""
        self.logger.info("清理所有防火墙规则")

        # 方法1：尝试根据内存记录删除容器规则
        for container_id in list(self.active_rules.keys()):
            self.remove_container_rules(container_id)

        # 方法2：强制清空所有链（确保彻底清理IPv4和IPv6）
        self._flush_all_chains()

        # 方法3：清理IPv6基础规则
        self._cleanup_ipv6_base_rules()

        # 清理Service规则
        self._cleanup_all_service_rules()

        # 清空内存记录
        self.active_rules.clear()
        self.active_service_rules.clear()
        self.logger.info("防火墙规则清理完成")
            
    def get_active_rules_count(self) -> int:
        """获取活跃规则数量"""
        return sum(len(rules) for rules in self.active_rules.values())

    def list_active_rules(self) -> List[FirewallRule]:
        """列出所有活跃规则"""
        all_rules = []
        for rules in self.active_rules.values():
            all_rules.extend(rules)
        return all_rules

    def add_service_rules(self, service_id: str, service_name: str,
                         service_ports: List[Dict], containers: List[Dict]):
        """为Service添加防火墙和NAT规则"""
        # 检查是否需要更新规则
        if service_id in self.active_service_rules:
            # 比较现有规则与新配置，如果有变化则先移除旧规则
            if self._service_rules_changed(service_id, service_ports, containers):
                self.logger.info(f"检测到Service {service_name} 配置变化，更新规则")
                self.remove_service_rules(service_id)
            else:
                self.logger.debug(f"Service {service_name} 的规则无变化，跳过")
                return

        rules = []

        for container in containers:
            container_id = container.get('container_id')
            container_name = container.get('container_name')
            container_ipv6 = container.get('ipv6_address')

            if not container_ipv6:
                self.logger.warning(f"容器 {container_name} 没有IPv6地址，跳过Service规则")
                continue

            for port_info in service_ports:
                # 从Service inspect中动态获取协议
                protocol = port_info.get('protocol', 'tcp').lower()
                published_port = port_info.get('published_port')
                target_port = port_info.get('target_port')

                if published_port and target_port:
                    rule = ServiceRule(
                        service_id=service_id,
                        service_name=service_name,
                        container_id=container_id,
                        container_name=container_name,
                        protocol=protocol,  # 动态协议，不写死
                        published_port=published_port,
                        target_port=target_port,
                        container_ipv6=container_ipv6,
                        interface_in=self.config.parent_interface,
                        interface_out=self.config.gateway_macvlan
                    )

                    if self._add_service_rule(rule):
                        rules.append(rule)

        if rules:
            self.active_service_rules[service_id] = rules
            self.logger.info(f"为Service {service_name} 添加了 {len(rules)} 条规则")

            # 记录详细的规则信息便于调试
            for rule in rules:
                self.logger.debug(f"  Service规则: {rule.protocol}:{rule.published_port}->{rule.target_port} -> {rule.container_ipv6}")
        else:
            self.logger.debug(f"Service {service_name} 没有生成有效规则")

    def _service_rules_changed(self, service_id: str, new_service_ports: List[Dict],
                              new_containers: List[Dict]) -> bool:
        """检测Service规则是否发生变化"""
        if service_id not in self.active_service_rules:
            return True  # 没有现有规则，需要添加

        existing_rules = self.active_service_rules[service_id]

        # 构建新规则的特征集合用于比较
        new_rule_signatures = set()
        for container in new_containers:
            container_ipv6 = container.get('ipv6_address')
            if not container_ipv6:
                continue

            for port_info in new_service_ports:
                protocol = port_info.get('protocol', 'tcp').lower()
                published_port = port_info.get('published_port')
                target_port = port_info.get('target_port')

                if published_port and target_port:
                    # 创建规则特征：协议_发布端口_目标端口_容器IPv6
                    signature = f"{protocol}_{published_port}_{target_port}_{container_ipv6}"
                    new_rule_signatures.add(signature)

        # 构建现有规则的特征集合
        existing_rule_signatures = set()
        for rule in existing_rules:
            signature = f"{rule.protocol}_{rule.published_port}_{rule.target_port}_{rule.container_ipv6}"
            existing_rule_signatures.add(signature)

        # 比较两个集合是否相同
        rules_changed = new_rule_signatures != existing_rule_signatures

        if rules_changed:
            self.logger.info(f"Service {service_id} 规则变化检测:")
            self.logger.info(f"  现有规则: {existing_rule_signatures}")
            self.logger.info(f"  新规则: {new_rule_signatures}")

        return rules_changed

    def _build_service_forward_rule(self, rule: ServiceRule, action: str) -> List[str]:
        """构建Service FORWARD规则"""
        return [
            action, self.config.chain_name,
            "-p", rule.protocol,
            "-d", rule.container_ipv6,  # 添加目标地址
            "--dport", str(rule.published_port),
            "-i", rule.interface_in,
            "-o", rule.interface_out,
            "-j", "ACCEPT"
        ]

    def _build_service_nat_rule(self, rule: ServiceRule, action: str) -> List[str]:
        """构建Service NAT规则 - 统一的规则构建逻辑"""
        return [
            "-t", "nat",
            action, self.config.nat_chain_name,
            "-i", rule.interface_in,
            "-d", rule.container_ipv6,
            "-p", rule.protocol,
            "--dport", str(rule.published_port),
            "-j", "DNAT",
            "--to-destination", f"[{rule.container_ipv6}]:{rule.target_port}"
        ]

    def _add_service_rule(self, rule: ServiceRule) -> bool:
        """添加单条Service规则（FORWARD + NAT）"""
        try:
            # 1. 添加FORWARD规则
            forward_rule = self._build_service_forward_rule(rule, "-A")
            if not self._rule_exists("ip6tables", forward_rule):
                subprocess.run(["ip6tables"] + forward_rule, check=True)
                self.logger.info(f"添加Service FORWARD规则: {rule}")

            # 2. 添加NAT规则
            nat_rule = self._build_service_nat_rule(rule, "-A")
            if not self._rule_exists("ip6tables", nat_rule):
                subprocess.run(["ip6tables"] + nat_rule, check=True)
                self.logger.info(f"添加Service NAT规则: {rule.protocol}/{rule.published_port}->{rule.target_port}")

            return True

        except subprocess.CalledProcessError as e:
            self.logger.error(f"添加Service规则失败: {rule}, 错误: {e}")
            return False

    def remove_service_rules(self, service_id: str):
        """移除Service的防火墙和NAT规则"""
        if service_id not in self.active_service_rules:
            return

        rules = self.active_service_rules[service_id]
        removed_count = 0

        for rule in rules:
            if self._remove_service_rule(rule):
                removed_count += 1

        del self.active_service_rules[service_id]
        self.logger.info(f"移除Service {rules[0].service_name} 的 {removed_count} 条规则")

    def _remove_service_rule(self, rule: ServiceRule) -> bool:
        """移除单条Service规则（FORWARD + NAT）"""
        success = True

        try:
            # 1. 移除FORWARD规则
            forward_check = self._build_service_forward_rule(rule, "-C")
            check_result = subprocess.run(["ip6tables"] + forward_check,
                                        capture_output=True, text=True)

            if check_result.returncode == 0:
                forward_delete = self._build_service_forward_rule(rule, "-D")
                subprocess.run(["ip6tables"] + forward_delete, check=True)
                self.logger.info(f"移除Service FORWARD规则: {rule}")
            else:
                self.logger.debug(f"Service FORWARD规则不存在: {rule}")

        except subprocess.CalledProcessError as e:
            self.logger.warning(f"移除Service FORWARD规则失败: {rule}, 错误: {e}")
            success = False

        try:
            # 2. 移除NAT规则
            nat_check = self._build_service_nat_rule(rule, "-C")
            check_result = subprocess.run(["ip6tables"] + nat_check,
                                        capture_output=True, text=True)

            if check_result.returncode == 0:
                nat_delete = self._build_service_nat_rule(rule, "-D")
                subprocess.run(["ip6tables"] + nat_delete, check=True)
                self.logger.info(f"移除Service NAT规则: {rule.protocol}/{rule.published_port}->{rule.target_port}")
            else:
                self.logger.debug(f"Service NAT规则不存在: {rule}")

        except subprocess.CalledProcessError as e:
            self.logger.warning(f"移除Service NAT规则失败: {rule}, 错误: {e}")
            success = False

        return success

    def _cleanup_all_service_rules(self):
        """清理所有Service规则"""
        if not self.active_service_rules:
            return

        self.logger.info("清理所有Service规则")

        for service_id in list(self.active_service_rules.keys()):
            self.remove_service_rules(service_id)

    def sync_rules_with_reality(self):
        """同步内存中的规则状态与实际防火墙规则"""
        self.logger.info("同步防火墙规则状态")

        try:
            # 获取当前链中的所有规则
            result = subprocess.run(["ip6tables", "-L", self.config.chain_name, "-n", "--line-numbers"],
                                  capture_output=True, text=True)

            if result.returncode != 0:
                self.logger.warning("无法读取防火墙规则，可能链不存在")
                return

            current_rules = result.stdout
            self.logger.debug(f"当前防火墙规则:\n{current_rules}")

            # 收集所有已知的容器IPv6地址和端口
            known_container_ips = set()
            known_container_ports = set()
            for rules in self.active_rules.values():
                for rule in rules:
                    known_container_ips.add(rule.ipv6_address)
                    known_container_ports.add(str(rule.port))

            # 收集所有已知的Service IPv6地址和发布端口
            known_service_ips = set()
            known_service_ports = set()
            for rules in self.active_service_rules.values():
                for rule in rules:
                    known_service_ips.add(rule.container_ipv6)
                    known_service_ports.add(str(rule.published_port))

            # 调试信息
            self.logger.debug(f"已知容器IP: {known_container_ips}")
            self.logger.debug(f"已知容器端口: {known_container_ports}")
            self.logger.debug(f"已知Service IP: {known_service_ips}")
            self.logger.debug(f"已知Service端口: {known_service_ports}")

            # 分别统计容器规则和Service规则
            lines = current_rules.split('\n')
            container_rule_count = 0
            service_rule_count = 0

            for line in lines:
                # 检查是否包含端口规则（支持所有协议）
                if ' dpt:' in line and 'ACCEPT' in line:
                    # 提取目标地址和端口
                    parts = line.strip().split()
                    if len(parts) >= 6:
                        destination = parts[5] if len(parts) > 5 else ""

                        # 查找端口信息
                        port_info = ""
                        for part in parts:
                            if 'dpt:' in part:
                                port_info = part
                                break

                        if port_info:
                            port = port_info.split('dpt:')[1] if 'dpt:' in port_info else ""

                            # 调试信息
                            self.logger.debug(f"解析规则: 目标={destination}, 端口={port}")

                            # 判断是容器规则还是Service规则
                            if destination in known_container_ips and port in known_container_ports:
                                container_rule_count += 1
                                self.logger.debug(f"识别为容器规则: {destination}:{port}")
                            elif destination in known_service_ips and port in known_service_ports:
                                service_rule_count += 1
                                self.logger.debug(f"识别为Service规则: {destination}:{port}")
                            else:
                                self.logger.debug(f"未识别规则: {destination}:{port}")

            # 统计内存中的规则数量
            memory_container_count = sum(len(rules) for rules in self.active_rules.values())
            memory_service_count = sum(len(rules) for rules in self.active_service_rules.values())

            # 分别检查容器规则和Service规则的一致性
            container_consistent = container_rule_count == memory_container_count
            service_consistent = service_rule_count == memory_service_count

            if container_consistent and service_consistent:
                self.logger.info(f"规则状态一致: {container_rule_count}条容器规则, {service_rule_count}条Service规则")
            else:
                if not container_consistent:
                    self.logger.warning(f"容器规则不一致: 防火墙中有{container_rule_count}条，内存中记录{memory_container_count}条")
                if not service_consistent:
                    self.logger.warning(f"Service规则不一致: 防火墙中有{service_rule_count}条，内存中记录{memory_service_count}条")
                self.logger.info("建议重启服务以确保状态一致")

        except Exception as e:
            self.logger.error(f"同步规则状态失败: {e}")

    def force_cleanup_all_container_rules(self):
        """强制清理所有容器相关的规则（基于规则特征识别）"""
        self.logger.info("强制清理所有容器规则")

        try:
            # 检查链是否存在
            check_result = subprocess.run(["ip6tables", "-L", self.config.chain_name],
                                        capture_output=True, text=True)
            if check_result.returncode != 0:
                self.logger.debug(f"防火墙链 {self.config.chain_name} 不存在")
                return

            # 获取当前链中的所有规则
            result = subprocess.run(["ip6tables", "-L", self.config.chain_name, "-n", "--line-numbers"],
                                  capture_output=True, text=True)

            if result.returncode != 0:
                self.logger.warning("无法获取防火墙规则列表")
                return

            lines = result.stdout.split('\n')
            deleted_count = 0

            # 从后往前删除（避免行号变化）
            for line in reversed(lines):
                # 只删除容器和Service规则（有端口特征的）
                if ' dpt:' in line and 'ACCEPT' in line:
                    # 提取行号
                    parts = line.strip().split()
                    if parts and parts[0].isdigit():
                        line_num = parts[0]
                        try:
                            # 再次确认规则存在后删除
                            check_cmd = ["ip6tables", "-L", self.config.chain_name, line_num]
                            check_result = subprocess.run(check_cmd, capture_output=True, text=True)

                            if check_result.returncode == 0:
                                subprocess.run(["ip6tables", "-D", self.config.chain_name, line_num],
                                             check=True, capture_output=True)
                                self.logger.info(f"删除容器规则行 {line_num}: {line.strip()}")
                                deleted_count += 1
                        except subprocess.CalledProcessError as e:
                            self.logger.warning(f"删除规则行 {line_num} 失败: {e}")

            self.logger.info(f"强制清理完成，删除了 {deleted_count} 条容器规则")

        except Exception as e:
            self.logger.error(f"强制清理容器规则失败: {e}")

        # 清空内存记录
        self.active_rules.clear()
