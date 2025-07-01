# Contributing to Docker IPv6 Firewall Manager

感谢您对 Docker IPv6 Firewall Manager 项目的关注！我们欢迎各种形式的贡献。

## 如何贡献

### 报告问题

如果您发现了 bug 或有功能建议，请：

1. 检查 [Issues](../../issues) 确保问题尚未被报告
2. 创建新的 Issue，包含：
   - 清晰的问题描述
   - 重现步骤
   - 期望的行为
   - 实际的行为
   - 系统环境信息
   - 相关日志

### 提交代码

1. **Fork 项目**
2. **创建功能分支**：`git checkout -b feature/amazing-feature`
3. **提交更改**：`git commit -m 'Add amazing feature'`
4. **推送分支**：`git push origin feature/amazing-feature`
5. **创建 Pull Request**

### 代码规范

- 使用 Python 3.9+ 语法
- 遵循 PEP 8 代码风格
- 添加适当的注释和文档字符串
- 为新功能编写测试
- 确保所有测试通过

### 测试

运行测试前请确保安装了依赖：

```bash
# 安装依赖
sudo apt-get install python3-docker python3-yaml

# 运行测试
python3 test/test_firewall.py

# 构建测试
./build.sh
```

### 文档

- 更新相关的 Markdown 文档
- 确保配置文件有适当的注释
- 更新 ARCHITECTURE.md 如果涉及架构变更

## 开发环境设置

### 系统要求

- Debian 12 或兼容系统
- Docker Engine
- Python 3.9+
- ip6tables
- systemd

### 本地开发

```bash
# 克隆项目
git clone <repository-url>
cd docker-ipv6-firewall

# 安装依赖
sudo apt-get install python3-docker python3-yaml

# 运行测试
python3 test/test_firewall.py

# 本地测试（需要 root 权限）
sudo python3 src/main.py
```

## 发布流程

1. 更新版本号在 `debian/control`
2. 更新 `CHANGELOG.md`
3. 运行完整测试
4. 构建 Debian 包：`./build.sh`
5. 测试安装包
6. 创建 Git tag
7. 发布 Release

## 代码审查

所有的 Pull Request 都需要经过代码审查。审查重点：

- 代码质量和可读性
- 安全性考虑
- 性能影响
- 向后兼容性
- 测试覆盖率
- 文档完整性

## 社区准则

- 保持友善和专业
- 尊重不同观点
- 专注于建设性的讨论
- 帮助新贡献者

## 许可证

通过贡献代码，您同意您的贡献将在 MIT 许可证下发布。

## 联系方式

如有问题，请通过以下方式联系：

- 创建 Issue
- 发送邮件到项目维护者

感谢您的贡献！
