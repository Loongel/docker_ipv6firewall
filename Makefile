# Docker IPv6 Firewall Manager Makefile

.PHONY: help install uninstall build test clean deps check lint format version

# 默认目标
help:
	@echo "Docker IPv6 Firewall Manager - 可用命令："
	@echo ""
	@echo "  make deps     - 安装系统依赖"
	@echo "  make test     - 运行测试"
	@echo "  make check    - 代码检查"
	@echo "  make build    - 构建 Debian 包"
	@echo "  make install  - 安装服务"
	@echo "  make uninstall- 卸载服务"
	@echo "  make clean    - 清理构建文件"
	@echo "  make format   - 格式化代码"
	@echo "  make lint     - 代码静态检查"
	@echo ""
	@echo "版本管理："
	@echo "  make version           - 显示当前版本"
	@echo "  make version-set V=x.y.z - 设置版本号"
	@echo "  make version-bump-major - 递增主版本号"
	@echo "  make version-bump-minor - 递增次版本号"
	@echo "  make version-bump-patch - 递增补丁版本号"
	@echo ""

# 安装系统依赖
deps:
	@echo "安装系统依赖..."
	apt-get update
	apt-get install -y python3 python3-docker python3-yaml iptables systemd
	@echo "依赖安装完成"

# 运行测试
test:
	@echo "运行测试..."
	python3 test/test_firewall.py
	@echo "测试完成"

# 代码检查
check:
	@echo "检查配置文件语法..."
	python3 -c "import yaml; yaml.safe_load(open('config/config.yaml'))"
	@echo "检查 Python 语法..."
	python3 -m py_compile src/*.py
	@echo "检查完成"

# 构建 Debian 包
build: check
	@echo "构建 Debian 包..."
	./build.sh
	@echo "构建完成"

# 安装服务
install: build
	@echo "安装 Docker IPv6 Firewall Manager..."
	dpkg -i docker-ipv6-firewall_*.deb || apt-get install -f
	@echo "安装完成"

# 卸载服务
uninstall:
	@echo "卸载 Docker IPv6 Firewall Manager..."
	systemctl stop docker-ipv6-firewall || true
	systemctl disable docker-ipv6-firewall || true
	dpkg -r docker-ipv6-firewall || true
	@echo "卸载完成"

# 清理构建文件
clean:
	@echo "清理构建文件..."
	rm -rf build/
	rm -f docker-ipv6-firewall_*.deb
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@echo "清理完成"

# 格式化代码（如果安装了 black）
format:
	@if command -v black >/dev/null 2>&1; then \
		echo "格式化 Python 代码..."; \
		black src/ test/; \
		echo "格式化完成"; \
	else \
		echo "未安装 black，跳过代码格式化"; \
		echo "安装命令：pip3 install black"; \
	fi

# 代码静态检查（如果安装了 flake8）
lint:
	@if command -v flake8 >/dev/null 2>&1; then \
		echo "运行代码静态检查..."; \
		flake8 src/ test/ --max-line-length=88 --ignore=E203,W503; \
		echo "静态检查完成"; \
	else \
		echo "未安装 flake8，跳过静态检查"; \
		echo "安装命令：pip3 install flake8"; \
	fi

# 开发环境设置
dev-setup: deps
	@echo "设置开发环境..."
	@if command -v pip3 >/dev/null 2>&1; then \
		pip3 install black flake8 --break-system-packages || \
		echo "无法安装开发工具，请手动安装 black 和 flake8"; \
	fi
	@echo "开发环境设置完成"

# 快速测试（不需要 root）
quick-test:
	@echo "运行快速测试（跳过需要 root 权限的测试）..."
	@python3 -c "\
import sys; \
sys.path.insert(0, 'src'); \
from config import Config; \
print('✓ 配置模块加载成功'); \
config = Config(); \
print('✓ 配置加载成功'); \
print('配置摘要：'); \
print(f'  物理接口: {config.parent_interface}'); \
print(f'  网关接口: {config.gateway_macvlan}'); \
print(f'  监控网络: {config.monitored_networks}'); \
"
	@echo "快速测试完成"

# 显示服务状态
status:
	@echo "Docker IPv6 Firewall Manager 状态："
	@systemctl is-active docker-ipv6-firewall && echo "✓ 服务运行中" || echo "✗ 服务未运行"
	@systemctl is-enabled docker-ipv6-firewall && echo "✓ 开机自启动已启用" || echo "✗ 开机自启动未启用"
	@if [ -f /var/log/docker-ipv6-firewall.log ]; then \
		echo "✓ 日志文件存在"; \
		echo "最近日志："; \
		tail -5 /var/log/docker-ipv6-firewall.log; \
	else \
		echo "✗ 日志文件不存在"; \
	fi

# 显示防火墙规则
show-rules:
	@echo "当前 IPv6 防火墙规则："
	@ip6tables -L DOCKER_IPV6_FORWARD -n -v 2>/dev/null || echo "防火墙链不存在"

# 管理工具快捷方式
manage-status:
	@./scripts/manage.sh status

manage-sync:
	@./scripts/manage.sh sync

manage-reset:
	@./scripts/manage.sh reset

manage-clean:
	@./scripts/manage.sh clean

# 配置管理快捷方式
config-validate:
	@python3 scripts/validate-config.py --verbose

config-reload:
	@./scripts/manage.sh reload

# 版本管理
version:
	@./scripts/version.sh get

version-set:
	@if [ -z "$(V)" ]; then \
		echo "错误: 请提供版本号，例如: make version-set V=1.3.0"; \
		exit 1; \
	fi
	@./scripts/version.sh set $(V)

version-bump-major:
	@./scripts/version.sh bump major

version-bump-minor:
	@./scripts/version.sh bump minor

version-bump-patch:
	@./scripts/version.sh bump patch
