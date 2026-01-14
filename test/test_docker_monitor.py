# tests/test_docker_monitor.py
import sys
import pytest
from unittest import mock

# Ensure src/ is importable
import os
TEST_DIR = os.path.dirname(__file__)
REPO_ROOT = os.path.abspath(os.path.join(TEST_DIR, ".."))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from docker_monitor import DockerMonitor


class DummyConfig:
    def __init__(self):
        self.docker_socket = "unix:///var/run/docker.sock"
        self.monitored_networks = ["macvlan", "bridge"]


class DummyFirewallManager:
    pass


@pytest.fixture
def monitor():
    cfg = DummyConfig()
    fm = DummyFirewallManager()
    dm = DockerMonitor(cfg, fm)
    # avoid real Docker client creation in tests
    dm.client = mock.MagicMock()
    return dm


def test_extract_custom_firewall_ports_parsing(monitor):
    labels = {
        "docker-ipv6-firewall.ports": "809/tcp, 443:444/udp, 5000"
    }
    parsed = monitor._extract_custom_firewall_ports(labels)
    # check that parsed contains expected entries (protocol normalization)
    assert any(p['external_port'] == 809 and p['internal_port'] == 809 and p['protocol'] == 'tcp' for p in parsed)
    assert any(p['external_port'] == 443 and p['internal_port'] == 444 and p['protocol'] == 'udp' for p in parsed)
    assert any(p['external_port'] == 5000 and p['internal_port'] == 5000 for p in parsed)


def test_derive_service_ports_from_containers_with_port_bindings(monitor):
    # Prepare two fake containers with port bindings and network ports
    # We will monkeypatch _get_container_info to return desired inspect data
    container_info1 = {
        'host_config': {
            'PortBindings': {
                '80/tcp': [{'HostPort': '8080', 'HostIp': ''}]
            }
        },
        'network_settings': {
            'Ports': {}
        }
    }
    container_info2 = {
        'host_config': {
            'PortBindings': {}
        },
        'network_settings': {
            'Ports': {
                '443/tcp': [{'HostPort': '0', 'HostIp': ''}],  # no host binding -> publish=target
                '53/udp': [{'HostPort': '8053', 'HostIp': ''}]
            }
        }
    }

    # Mock client.containers.list to return two dummy container objects (we only pass them to _get_container_info)
    fake_container1 = mock.MagicMock()
    fake_container2 = mock.MagicMock()
    monitor.client.containers.list.return_value = [fake_container1, fake_container2]

    # Monkeypatch _get_container_info to return above dicts in order
    infos = [container_info1, container_info2]
    def get_info_side_effect(container):
        return infos.pop(0)
    monitor._get_container_info = mock.MagicMock(side_effect=get_info_side_effect)

    derived = monitor._derive_service_ports_from_containers("dummy-service")
    # Expect entries for:
    # - tcp: published 8080 -> target 80
    # - tcp: published 443 -> target 443 (since HostPort is 0 -> fallback to target)
    # - udp: published 8053 -> target 53
    sigs = {f"{p['protocol']}_{p['published_port']}_{p['target_port']}" for p in derived}
    assert "tcp_8080_80" in sigs
    assert "tcp_443_443" in sigs
    assert "udp_8053_53" in sigs


def test_get_service_info_fallback_to_container_labels(monitor):
    # Simulate subprocess.run failing (CalledProcessError) when running `docker service inspect`.
    import subprocess
    monitor.client.containers.list.return_value = [mock.MagicMock()]
    # make _get_container_info return labels with com.docker.swarm.service.id
    monitor._get_container_info = mock.MagicMock(return_value={
        'config': {
            'Labels': {
                'com.docker.swarm.service.id': 'svc-1234',
                'com.docker.swarm.service.name': 'svc-name'
            }
        }
    })

    # patch subprocess.run to raise CalledProcessError for service inspect
    with mock.patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, ['docker'])):
        svc_info = monitor._get_service_info('svc-name')

    assert svc_info is not None
    assert svc_info['id'] == 'svc-1234'
    assert svc_info['name'] == 'svc-name'