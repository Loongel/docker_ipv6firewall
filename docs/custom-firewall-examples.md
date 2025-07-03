# Custom Firewall Ports Examples

## Single Port

### Basic Port (TCP default)
```yaml
web:
  image: nginx:alpine
  networks: [macvlan_ipv46_swarm]
  labels:
    - "docker-ipv6-firewall.ports=80"
```

### Specific Protocol
```yaml
dns:
  image: bind9:latest
  networks: [macvlan_ipv46_swarm]
  labels:
    - "docker-ipv6-firewall.ports=53/udp"
```

### All Protocols
```yaml
proxy:
  image: haproxy:latest
  networks: [macvlan_ipv46_swarm]
  labels:
    - "docker-ipv6-firewall.ports=8080/all"
```

## Port Mapping

### signle Port Mapping
```yaml
web:
  image: nginx:alpine
  networks: [macvlan_ipv46_swarm]
  labels:
    - "docker-ipv6-firewall.ports=8443:443/tcp"
```
## Multiple Ports
```yaml
web:
  image: nginx:alpine
  networks: [macvlan_ipv46_swarm]
  labels:
    - "docker-ipv6-firewall.ports=80,443"
```

### Mixed Protocols
```yaml
app:
  image: myapp:latest
  networks: [macvlan_ipv46_swarm]
  labels:
    - "docker-ipv6-firewall.ports=80/tcp,53/udp,8080/all"
```

### Complex Mapping
```yaml
app:
  image: myapp:latest
  networks: [macvlan_ipv46_swarm]
  labels:
    - "docker-ipv6-firewall.ports=8080:80/tcp,8443:443/tcp,5353:53/udp"
```
