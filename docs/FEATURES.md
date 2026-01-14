# Features & Advanced Usage

## 1. Safety & Isolation (安全与隔离)

防火墙不仅负责“放行”流量，更重要的是“拦截”非法流量。

### 1.1 严格的白名单机制
工具采用 **默认拒绝 (Default Deny)** 策略。
- 只有被明确记录的容器端口才会被放行。
- 只有来自 macvlan 网关或物理接口的合法流量才会被转发。

### 1.2 容器隔离 (Container Isolation)
为了防止容器之间的非法 IPv6 互访（这在 macvlan 网络中是一个常见安全隐患），工具默认会添加隔离规则：
```bash
# 禁止 macvlan 网络内部容器互访 IPv6
ip6tables -A DOCKER_IPV6FW_FORWARD -i macvlan_gw -o macvlan_gw -j DROP
```
*注：可通过 `config.yaml` 调整此行为。*

---

## 2. Swarm Worker Node Support (集群工作节点支持)

本工具专为 Docker Swarm 环境优化，无论是在 Manager 节点还是 Worker 节点，都能正常工作。

### 2.1 优雅降级 (Graceful Degradation)
在 Worker 节点上，由于缺乏 Manager 权限，无法执行 `docker service inspect`。工具会自动检测此情况并启用降级模式：
1. **本地发现**: 放弃查询 Swarm API，改为扫描本地运行的容器。
2. **标签推导**: 利用容器自带的 `com.docker.swarm.service.*` 标签反向推导 Service 信息。
3. **功能保留**: 尽管无法获取全局 Service 信息（如 VIP），但对于“让外部访问本地容器”这一核心需求，功能完全保留。

---

## 3. Exclusive Mode (独占模式)

这是解决端口冲突和实现高级流量控制的核心功能。

### 3.1 逻辑说明
当一个 Service 或容器定义了 `docker-ipv6-firewall.ports` 标签时，工具进入 **独占模式**：
- **忽略原生端口**: Dockerfile `EXPOSE` 或 `docker run -p` 定义的所有端口映射都将被**忽略**。
- **仅用 Label**: 防火墙只为 Label 中显式定义的端口生成规则。

### 3.2 使用场景
- **隐藏管理端口**: 容器暴露了 8080 (应用) 和 9090 (管理)，通过 Label 只放行 8080，对外隐藏 9090。
- **端口重映射**: 容器监听 80，但外部希望通过 5443 访问。使用 Label `5443:80` 实现 NAT 映射。

### 3.3 示例
在 `docker-compose.yml` 中：
```yaml
services:
  web:
    image: nginx
    ports:
      - "80:80"   # 原生映射 (将被忽略)
    deploy:
      labels:
        # 定义后，仅 8080 可访问，80 端口被防火墙拦截
        - "docker-ipv6-firewall.ports=8080:80"
```

---

## 4. Exemptions (豁免机制)

目前暂未提供基于 IP 的豁免白名单功能。所有访问控制基于端口。如果需要特定 IP 的访问控制，建议结合系统的 `ip6tables` 额外规则使用。
