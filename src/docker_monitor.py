#!/usr/bin/env python3
"""
Docker容器监控模块
"""

import docker
import logging
import subprocess
import threading
import time
from typing import Dict, List, Any


class DockerMonitor:
    """Docker容器监控器"""
    
    def __init__(self, config, firewall_manager):
        self.config = config
        self.firewall_manager = firewall_manager
        self.logger = logging.getLogger(__name__)
        self.client = None
        self.monitor_thread = None
        self.running = False
        
    def start(self):
        """启动监控"""
        try:
            self.client = docker.DockerClient(base_url=self.config.docker_socket)
            self.client.ping()  # 测试连接
            self.logger.info("Docker连接成功")
            
            # 处理现有容器
            self._process_existing_containers()

            # 处理现有Services
            self._process_existing_services()

            # 启动事件监控线程
            self.running = True
            self.monitor_thread = threading.Thread(target=self._monitor_events)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()

            # 启动周期性扫描线程（兜底机制）
            self.scan_thread = threading.Thread(target=self._periodic_scan)
            self.scan_thread.daemon = True
            self.scan_thread.start()

            self.logger.info("Docker监控已启动")
            
        except Exception as e:
            self.logger.error(f"启动Docker监控失败: {e}")
            raise
            
    def stop(self):
        """停止监控"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        if hasattr(self, 'scan_thread') and self.scan_thread:
            self.scan_thread.join(timeout=5)
        if self.client:
            self.client.close()
        self.logger.info("Docker监控已停止")
        
    def _process_existing_containers(self):
        """处理现有的运行中容器"""
        try:
            containers = self.client.containers.list(all=False)  # 只获取运行中的容器
            self.logger.info(f"发现 {len(containers)} 个运行中的容器")
            
            for container in containers:
                self._handle_container_start(container.id)
                
        except Exception as e:
            self.logger.error(f"处理现有容器失败: {e}")
            
    def _monitor_events(self):
        """监控Docker事件"""
        self.logger.info("开始监控Docker事件")
        
        try:
            for event in self.client.events(decode=True):
                if not self.running:
                    break
                    
                if event.get('Type') == 'container':
                    action = event.get('Action')
                    container_id = event.get('id')

                    if action == 'start':
                        self.logger.debug(f"容器启动事件: {container_id}")
                        self._handle_container_start(container_id)
                    elif action in ['stop', 'die', 'kill']:
                        self.logger.debug(f"容器停止事件: {container_id}")
                        self._handle_container_stop(container_id)

                elif event.get('Type') == 'service':
                    action = event.get('Action')
                    service_id = event.get('id')

                    if action == 'remove':
                        self.logger.debug(f"Service删除事件: {service_id}")
                        self._handle_service_remove(service_id)
                        
        except Exception as e:
            if self.running:
                self.logger.error(f"监控Docker事件失败: {e}")
                # 重新连接Docker并重试
                try:
                    self.client.close()
                    self.client = docker.DockerClient(base_url=self.config.docker_socket)
                    self.client.ping()
                    self.logger.info("Docker重新连接成功")
                except Exception as reconnect_error:
                    self.logger.error(f"Docker重新连接失败: {reconnect_error}")

                time.sleep(5)
                if self.running:
                    self._monitor_events()

    def _periodic_scan(self):
        """周期性扫描（兜底机制）- 每1分钟检查一次状态一致性"""
        import time

        while self.running:
            try:
                time.sleep(60)  # 1分钟
                if not self.running:
                    break

                self.logger.info("执行周期性扫描（兜底机制）- 检查容器和Service状态一致性")

                # 清理不存在的容器和Service规则
                self._cleanup_stale_rules()

                # 重新扫描现有容器和Service
                self._process_existing_containers()
                self._process_existing_services()

            except Exception as e:
                self.logger.error(f"周期性扫描失败: {e}")
                time.sleep(60)  # 出错时等待1分钟再重试

    def _handle_container_start(self, container_id: str):
        """处理容器启动事件"""
        try:
            container = self.client.containers.get(container_id)
            container_info = self._get_container_info(container)
            
            if container_info:
                self.logger.info(f"处理容器启动: {container_info['name']}")
                
                port_info = self._extract_container_ports(container_info)
                networks = container_info.get('networks', {})

                # 检查是否为Service容器
                labels = container_info.get('config', {}).get('Labels', {})
                service_name = labels.get('com.docker.swarm.service.name')

                # 如果是Service容器，尝试从Service配置中获取自定义防火墙端口
                if service_name and not port_info['custom_ports']:
                    service_custom_ports = self._get_service_custom_ports(service_name)
                    if service_custom_ports:
                        port_info['custom_ports'] = service_custom_ports
                        self.logger.debug(f"从Service {service_name} 获取自定义端口: {service_custom_ports}")

                if networks:
                    # 处理Public端口（容器级别的端口映射）
                    if port_info['public_ports']:
                        self.firewall_manager.add_container_public_rules(
                            container_id,
                            container_info['name'],
                            port_info['public_ports'],
                            networks
                        )

                    # 处理自定义防火墙端口
                    if port_info['custom_ports']:
                        self.firewall_manager.add_custom_firewall_rules(
                            container_id,
                            container_info['name'],
                            port_info['custom_ports'],
                            networks
                        )
                        self.logger.info(f"为容器 {container_info['name']} 处理自定义防火墙端口")

                    if not any([port_info['public_ports'], port_info['custom_ports']]):
                        self.logger.debug(f"容器 {container_info['name']} 无需要处理的端口")
                else:
                    self.logger.debug(f"容器 {container_info['name']} 无监控网络")

                # 检查是否是Service容器，如果是则触发Service处理
                self._check_and_handle_service_container(container_info)

        except Exception as e:
            self.logger.error(f"处理容器启动事件失败 {container_id}: {e}")
            
    def _handle_container_stop(self, container_id: str):
        """处理容器停止事件"""
        try:
            self.firewall_manager.remove_container_rules(container_id)
            self.logger.debug(f"处理容器停止: {container_id}")
            
        except Exception as e:
            self.logger.error(f"处理容器停止事件失败 {container_id}: {e}")

    def _handle_service_remove(self, service_id: str):
        """处理Service删除事件"""
        try:
            self.logger.info(f"处理Service删除事件: {service_id}")
            self.firewall_manager.remove_service_rules(service_id)
        except Exception as e:
            self.logger.error(f"处理Service删除事件失败 {service_id}: {e}")

    def _check_and_handle_service_container(self, container_info: Dict[str, Any]):
        """检查容器是否属于Service，如果是则处理对应的Service"""
        try:
            # 检查容器是否有Service标签
            labels = container_info.get('labels', {})
            service_name = labels.get('com.docker.swarm.service.name')

            if service_name:
                self.logger.debug(f"检测到Service容器: {container_info['name']} 属于Service: {service_name}")

                # 延迟一点时间确保容器完全启动
                import time
                time.sleep(2)

                # 触发Service处理
                self._handle_service_update(service_name)

        except Exception as e:
            self.logger.error(f"检查Service容器失败: {e}")

    def _cleanup_stale_rules(self):
        """清理不存在的容器和Service的陈旧规则"""
        try:
            # 获取当前存在的容器ID
            existing_containers = set()
            for container in self.client.containers.list(all=True):
                existing_containers.add(container.id)

            # 清理不存在的容器规则
            stale_container_ids = []
            for container_id in self.firewall_manager.active_rules.keys():
                if container_id not in existing_containers:
                    stale_container_ids.append(container_id)

            for container_id in stale_container_ids:
                self.logger.info(f"清理陈旧容器规则: {container_id}")
                self.firewall_manager.remove_container_rules(container_id)

            # 获取当前存在的Service ID
            existing_services = set()
            for service in self.client.services.list():
                existing_services.add(service.id)

            # 清理不存在的Service规则
            stale_service_ids = []
            for service_id in self.firewall_manager.active_service_rules.keys():
                if service_id not in existing_services:
                    stale_service_ids.append(service_id)

            for service_id in stale_service_ids:
                self.logger.info(f"清理陈旧Service规则: {service_id}")
                self.firewall_manager.remove_service_rules(service_id)

        except Exception as e:
            self.logger.error(f"清理陈旧规则失败: {e}")

    def _get_container_info(self, container) -> Dict[str, Any]:
        """获取容器详细信息"""
        try:
            # 重新获取最新的容器信息
            container.reload()
            
            # 获取inspect信息
            inspect_data = self.client.api.inspect_container(container.id)
            
            return {
                'id': container.id,
                'name': container.name,
                'status': container.status,
                'config': inspect_data.get('Config', {}),
                'host_config': inspect_data.get('HostConfig', {}),
                'network_settings': inspect_data.get('NetworkSettings', {}),
                'networks': inspect_data.get('NetworkSettings', {}).get('Networks', {})
            }
            
        except Exception as e:
            self.logger.error(f"获取容器信息失败 {container.id}: {e}")
            return None
            
    def _extract_container_ports(self, container_info: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """提取容器端口信息，智能分类处理不同网络模式"""
        result = {
            'public_ports': []   # Public端口映射
        }

        try:
            # 1. 检测网络模式
            network_mode = container_info.get('host_config', {}).get('NetworkMode', 'bridge')

            # 2. 获取基础端口信息
            port_bindings = container_info.get('host_config', {}).get('PortBindings', {})
            network_ports = container_info.get('network_settings', {}).get('Ports', {})

            # 3. 检查是否为Service容器和自定义防火墙配置
            labels = container_info.get('config', {}).get('Labels', {})
            is_service_container = 'com.docker.swarm.service.name' in labels

            # 检查自定义防火墙Labels
            custom_firewall_ports = self._extract_custom_firewall_ports(labels)

            self.logger.debug(f"端口提取 - 网络模式: {network_mode}, Service容器: {is_service_container}")
            self.logger.debug(f"端口绑定: {list(port_bindings.keys())}")

            # 4. 处理Public端口映射（优先级最高）
            public_port_set = set()

            # 优先使用PortBindings（配置时定义）
            if port_bindings:
                for port_spec, bindings in port_bindings.items():
                    if '/' in port_spec and bindings:
                        port_str, protocol = port_spec.split('/', 1)
                        try:
                            container_port = int(port_str)
                            host_port = int(bindings[0].get('HostPort', 0))
                            host_ip = bindings[0].get('HostIp', '')

                            if host_port > 0:
                                result['public_ports'].append({
                                    'container_port': container_port,
                                    'host_port': host_port,
                                    'host_ip': host_ip,
                                    'protocol': protocol,
                                    'type': 'public',
                                    'source': 'PortBindings'
                                })
                                public_port_set.add(f"{container_port}/{protocol}")

                        except (ValueError, IndexError, TypeError) as e:
                            self.logger.warning(f"无法解析端口绑定 {port_spec}: {e}")

            # 补充使用NetworkSettings.Ports（运行时状态）
            elif network_ports and network_mode == 'bridge':
                for port_spec, bindings in network_ports.items():
                    if '/' in port_spec and bindings:
                        port_str, protocol = port_spec.split('/', 1)
                        try:
                            container_port = int(port_str)
                            # 选择第一个有效绑定
                            for binding in bindings:
                                host_port = int(binding.get('HostPort', 0))
                                host_ip = binding.get('HostIp', '')

                                if host_port > 0:
                                    port_key = f"{container_port}/{protocol}"
                                    if port_key not in public_port_set:
                                        result['public_ports'].append({
                                            'container_port': container_port,
                                            'host_port': host_port,
                                            'host_ip': host_ip,
                                            'protocol': protocol,
                                            'type': 'public',
                                            'source': 'NetworkSettings'
                                        })
                                        public_port_set.add(port_key)
                                    break

                        except (ValueError, TypeError) as e:
                            self.logger.warning(f"无法解析网络端口 {port_spec}: {e}")

            # 5. Host网络模式特殊处理
            if network_mode == 'host':
                # Host模式下没有端口映射
                result['public_ports'] = []
                self.logger.debug("Host网络模式：清空Public端口")

        except Exception as e:
            self.logger.error(f"提取容器端口信息失败: {e}")

        # 6. 处理自定义防火墙端口配置
        if custom_firewall_ports:
            self.logger.debug(f"检测到自定义防火墙端口配置: {custom_firewall_ports}")
            result['custom_ports'] = custom_firewall_ports
        else:
            result['custom_ports'] = []

        self.logger.debug(f"端口提取结果 - Public: {len(result['public_ports'])}, Custom: {len(result['custom_ports'])}")
        return result

    def _extract_custom_firewall_ports(self, labels: Dict[str, str]) -> List[Dict[str, Any]]:
        """提取自定义防火墙端口配置"""
        custom_ports = []

        try:
            # 提取端口配置（不需要enable标志）
            ports_config = labels.get('docker-ipv6-firewall.ports', '')
            if not ports_config:
                return custom_ports

            # 解析端口配置，支持多种格式：
            # "809/tcp" - 简单端口
            # "809:80/tcp" - 端口映射
            # "809/tcp,443:444/tcp" - 多个端口
            for port_spec in ports_config.split(','):
                port_spec = port_spec.strip()
                if not port_spec:
                    continue

                try:
                    # 解析协议
                    if '/' in port_spec:
                        port_part, protocol = port_spec.rsplit('/', 1)
                    else:
                        port_part, protocol = port_spec, 'tcp'

                    # 解析端口映射
                    if ':' in port_part:
                        # 格式: "809:80" (外部端口:内部端口)
                        external_port_str, internal_port_str = port_part.split(':', 1)
                        external_port = int(external_port_str)
                        internal_port = int(internal_port_str)
                    else:
                        # 格式: "809" (端口相同)
                        external_port = internal_port = int(port_part)

                    custom_ports.append({
                        'external_port': external_port,
                        'internal_port': internal_port,
                        'protocol': protocol,
                        'type': 'custom_firewall'
                    })

                    self.logger.debug(f"解析自定义端口: {external_port}:{internal_port}/{protocol}")

                except (ValueError, IndexError) as e:
                    self.logger.warning(f"无法解析自定义防火墙端口配置 '{port_spec}': {e}")

        except Exception as e:
            self.logger.error(f"提取自定义防火墙端口配置失败: {e}")

        return custom_ports

    def _get_service_custom_ports(self, service_name: str) -> List[Dict[str, Any]]:
        """从Service配置中获取自定义防火墙端口"""
        try:
            # 获取Service配置
            result = subprocess.run(
                ['docker', 'service', 'inspect', service_name, '--format', '{{ json .Spec.TaskTemplate.ContainerSpec.Labels }}'],
                capture_output=True, text=True, timeout=10
            )

            if result.returncode != 0:
                self.logger.warning(f"无法获取Service {service_name} 配置: {result.stderr}")
                return []

            # 解析Service Labels
            import json
            service_labels = json.loads(result.stdout.strip())

            # 提取自定义防火墙端口配置
            return self._extract_custom_firewall_ports(service_labels)

        except Exception as e:
            self.logger.error(f"获取Service {service_name} 自定义端口失败: {e}")
            return []

    def _process_existing_services(self):
        """处理现有的Services"""
        try:
            # 获取本节点的Services
            local_services = self._get_local_services()
            self.logger.info(f"周期性扫描: 发现 {len(local_services)} 个本节点的Services，检查配置变化")

            for service_name in local_services:
                self._handle_service_update(service_name)

        except Exception as e:
            self.logger.error(f"处理现有Services失败: {e}")

    def _get_local_services(self) -> List[str]:
        """获取本节点的Services"""
        try:
            # 使用你提供的命令获取本节点Services
            import subprocess
            result = subprocess.run([
                'docker', 'ps',
                '--filter', 'label=com.docker.swarm.service.name',
                '--format', '{{.Names}}'
            ], capture_output=True, text=True, check=True)

            if result.stdout.strip():
                # 提取service名称（去掉实例后缀）
                service_names = []
                for line in result.stdout.strip().split('\n'):
                    service_name = line.split('.')[0]
                    if service_name not in service_names:
                        service_names.append(service_name)
                return service_names
            else:
                return []

        except subprocess.CalledProcessError as e:
            self.logger.error(f"获取本节点Services失败: {e}")
            return []
        except Exception as e:
            self.logger.error(f"解析Services列表失败: {e}")
            return []

    def _handle_service_update(self, service_name: str):
        """处理Service更新"""
        try:
            # 获取Service详细信息
            service_info = self._get_service_info(service_name)
            if not service_info:
                return

            # 获取Service的端口配置
            service_ports = self._extract_service_ports(service_info)
            if not service_ports:
                self.logger.debug(f"Service {service_name} 没有发布端口")
                return

            # 获取Service对应的本节点容器
            service_containers = self._get_service_containers(service_name)
            if not service_containers:
                self.logger.debug(f"Service {service_name} 在本节点没有容器")
                return

            self.logger.info(f"检查Service: {service_name}, 端口: {len(service_ports)}, 容器: {len(service_containers)}")

            # 记录端口详情便于调试
            port_details = []
            for port in service_ports:
                port_details.append(f"{port.get('protocol', 'tcp')}:{port.get('published_port')}->{port.get('target_port')}")
            self.logger.debug(f"Service {service_name} 端口映射: {', '.join(port_details)}")

            # 添加Service规则
            self.firewall_manager.add_service_rules(
                service_info['id'],
                service_name,
                service_ports,
                service_containers
            )

        except Exception as e:
            self.logger.error(f"处理Service {service_name} 失败: {e}")

    def _get_service_info(self, service_name: str) -> Dict[str, Any]:
        """获取Service详细信息"""
        try:
            import subprocess
            result = subprocess.run([
                'docker', 'service', 'inspect', service_name
            ], capture_output=True, text=True, check=True)

            import json
            service_data = json.loads(result.stdout)[0]

            return {
                'id': service_data.get('ID'),
                'name': service_data.get('Spec', {}).get('Name'),
                'endpoint': service_data.get('Endpoint', {}),
                'spec': service_data.get('Spec', {})
            }

        except subprocess.CalledProcessError as e:
            self.logger.error(f"获取Service {service_name} 信息失败: {e}")
            return None
        except Exception as e:
            self.logger.error(f"解析Service {service_name} 信息失败: {e}")
            return None

    def _extract_service_ports(self, service_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """提取Service端口配置"""
        ports = []

        try:
            endpoint_ports = service_info.get('endpoint', {}).get('Ports', [])

            for port in endpoint_ports:
                # 动态获取协议，不写死
                protocol = port.get('Protocol', 'tcp').lower()
                published_port = port.get('PublishedPort')
                target_port = port.get('TargetPort')
                publish_mode = port.get('PublishMode', 'ingress')

                if published_port and target_port and publish_mode == 'ingress':
                    ports.append({
                        'protocol': protocol,  # 动态协议
                        'published_port': published_port,
                        'target_port': target_port,
                        'publish_mode': publish_mode
                    })

        except Exception as e:
            self.logger.error(f"提取Service端口配置失败: {e}")

        return ports

    def _get_service_containers(self, service_name: str) -> List[Dict[str, Any]]:
        """获取Service对应的本节点容器"""
        containers = []

        try:
            # 获取属于该Service的本节点容器
            service_containers = self.client.containers.list(
                filters={'label': f'com.docker.swarm.service.name={service_name}'}
            )

            for container in service_containers:
                container_info = self._get_container_info(container)
                if container_info:
                    # 提取容器的IPv6地址
                    networks = container_info.get('networks', {})
                    for network_name, network_info in networks.items():
                        ipv6_address = network_info.get('GlobalIPv6Address')
                        if ipv6_address and self._should_monitor_network(network_name):
                            containers.append({
                                'container_id': container.id,
                                'container_name': container.name,
                                'ipv6_address': ipv6_address,
                                'network': network_name
                            })
                            break  # 只需要一个有效的IPv6地址

        except Exception as e:
            self.logger.error(f"获取Service {service_name} 容器失败: {e}")

        return containers

    def _should_monitor_network(self, network_name: str) -> bool:
        """检查是否应该监控该网络"""
        # 检查网络类型是否在监控列表中
        try:
            network = self.client.networks.get(network_name)
            network_driver = network.attrs.get('Driver', '')
            return network_driver in self.config.monitored_networks
        except Exception:
            return False
