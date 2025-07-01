#!/usr/bin/env python3
"""
Docker IPv6 Firewall Manager
自动管理Docker容器的IPv6防火墙规则
"""

import sys
import signal
import logging
import time
import threading
from pathlib import Path

from docker_monitor import DockerMonitor
from firewall_manager import FirewallManager
from config import Config


class DockerIPv6FirewallManager:
    """主服务类"""
    
    def __init__(self):
        self.config = Config()

        # 检查配置有效性
        if not self.config.is_valid():
            self._handle_invalid_config()

        self.setup_logging()
        self.firewall_manager = FirewallManager(self.config)
        self.docker_monitor = DockerMonitor(self.config, self.firewall_manager)
        self.running = False
        self.config_monitor_thread = None
        
    def setup_logging(self):
        """设置日志"""
        logging.basicConfig(
            level=getattr(logging, self.config.log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(self.config.log_file)
            ]
        )
        self.logger = logging.getLogger(__name__)

    def _handle_invalid_config(self):
        """处理无效配置"""
        print("配置验证失败:")
        for error in self.config.get_validation_errors():
            print(f"  - {error}")
        print("")
        print("服务将使用默认配置继续运行，但可能无法正常工作。")
        print("请修复配置文件后重启服务或使用热重载功能。")
        print("")

    def signal_handler(self, signum, frame):
        """信号处理器"""
        if hasattr(self, 'logger'):
            self.logger.info(f"收到信号 {signum}，正在停止服务...")
        else:
            print(f"收到信号 {signum}，正在停止服务...")
        self.stop()

    def reload_config_handler(self, signum, frame):
        """配置重载信号处理器"""
        if hasattr(self, 'logger'):
            self.logger.info("收到配置重载信号，正在重新加载配置...")
        else:
            print("收到配置重载信号，正在重新加载配置...")

        try:
            success, errors = self.config.reload_config()

            if success:
                if hasattr(self, 'logger'):
                    self.logger.info("配置重新加载成功")
                else:
                    print("配置重新加载成功")

                # 重新设置日志级别
                if hasattr(self, 'logger'):
                    logger = logging.getLogger()
                    logger.setLevel(getattr(logging, self.config.log_level.upper()))

            else:
                if hasattr(self, 'logger'):
                    self.logger.error("配置重新加载失败:")
                    for error in errors:
                        self.logger.error(f"  - {error}")
                else:
                    print("配置重新加载失败:")
                    for error in errors:
                        print(f"  - {error}")

        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"配置重载异常: {e}")
            else:
                print(f"配置重载异常: {e}")

    def _start_config_monitor(self):
        """启动配置文件监控线程"""
        self.config_monitor_thread = threading.Thread(target=self._monitor_config_changes)
        self.config_monitor_thread.daemon = True
        self.config_monitor_thread.start()
        self.logger.info("配置文件监控已启动")

    def _monitor_config_changes(self):
        """监控配置文件变化"""
        while self.running:
            try:
                if self.config.has_config_changed():
                    self.logger.info("检测到配置文件变化，正在重新加载...")
                    success, errors = self.config.reload_config()

                    if success:
                        self.logger.info("配置重新加载成功")
                        # 这里可以添加配置变化后的处理逻辑
                        # 例如重新初始化某些组件
                    else:
                        self.logger.error("配置重新加载失败:")
                        for error in errors:
                            self.logger.error(f"  - {error}")
                        self.logger.warning("继续使用旧配置运行")

                time.sleep(5)  # 每5秒检查一次
            except Exception as e:
                self.logger.error(f"配置监控异常: {e}")
                time.sleep(10)  # 出错时等待更长时间
        
    def start(self):
        """启动服务"""
        self.logger.info("启动 Docker IPv6 Firewall Manager")
        
        # 注册信号处理器
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGHUP, self.reload_config_handler)
        
        try:
            # 再次检查配置（可能在setup_logging后有更新）
            if not self.config.is_valid():
                self.logger.warning("配置验证失败，但服务将继续运行:")
                for error in self.config.get_validation_errors():
                    self.logger.warning(f"  - {error}")

            # 初始化防火墙规则
            self.firewall_manager.initialize()

            # 启动Docker监控
            self.docker_monitor.start()

            # 同步规则状态
            self.firewall_manager.sync_rules_with_reality()

            # 启动配置监控
            self._start_config_monitor()

            self.running = True
            self.logger.info("服务启动成功")

            # 主循环
            while self.running:
                time.sleep(1)
                
        except Exception as e:
            self.logger.error(f"服务启动失败: {e}")
            # 启动失败时也要清理
            self.stop()
            sys.exit(1)
        finally:
            # 确保在任何情况下都会清理
            if hasattr(self, 'firewall_manager'):
                try:
                    self.firewall_manager.cleanup()
                except:
                    pass
            
    def stop(self):
        """停止服务"""
        self.running = False

        # 停止配置监控
        if self.config_monitor_thread and self.config_monitor_thread.is_alive():
            self.config_monitor_thread.join(timeout=2)

        # 停止Docker监控
        if hasattr(self, 'docker_monitor'):
            self.docker_monitor.stop()

        # 清理防火墙规则
        if hasattr(self, 'firewall_manager'):
            try:
                self.firewall_manager.cleanup()
            except Exception as e:
                if hasattr(self, 'logger'):
                    self.logger.error(f"清理防火墙规则失败: {e}")
                else:
                    print(f"清理防火墙规则失败: {e}")

        if hasattr(self, 'logger'):
            self.logger.info("服务已停止")
        else:
            print("服务已停止")


def main():
    """主函数"""
    manager = DockerIPv6FirewallManager()
    manager.start()


if __name__ == "__main__":
    main()
