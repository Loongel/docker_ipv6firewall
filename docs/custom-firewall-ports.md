# Custom Firewall Ports

## Overview

Configure container port mappings via Docker labels without occupying host ports. Access containers directly through their IPv6 addresses.

## Configuration

### Basic Syntax
```yaml
labels:
  - "docker-ipv6-firewall.ports=<port_config>"
```

### Port Formats

| Format | Description | Example |
|--------|-------------|---------|
| `port` | Same port, TCP protocol | `80` |
| `port/protocol` | Same port, specific protocol | `80/tcp`, `53/udp`, `443/all` |
| `external:internal` | Port mapping, TCP protocol | `8080:80` |
| `external:internal/protocol` | Port mapping, specific protocol | `8080:80/tcp` |
| `port1,port2,port3` | Multiple ports | `80,443/tcp,853:53/udp` |

### Protocols

- `tcp` - TCP protocol (default)
- `udp` - UDP protocol
- `all` - Both TCP and UDP

## Examples

➡️ **[View Complete Examples](custom-firewall-examples.md)**

### Basic Usage
```yaml
web:
  image: nginx:alpine
  networks: [macvlan_ipv46_swarm]
  labels:
    - "docker-ipv6-firewall.ports=80"
```
## Access

```bash
# Custom firewall ports (direct container access)
curl -6 "[container_ipv6]:8080"
```

## Comparison

| Feature | Traditional `ports` | Custom Labels |
|---------|-------------------|---------------|
| Host port usage | ✅ Occupies | ❌ No occupation |
| Port conflicts | ⚠️ Possible | ✅ Avoided |
| IPv6 support | ✅ Yes | ✅ Native |
| Configuration | ⚠️ Limited | ✅ Flexible |

## Notes

- Container must be on monitored IPv6 network
- Configuration changes require container restart
- Invalid formats are ignored with warnings