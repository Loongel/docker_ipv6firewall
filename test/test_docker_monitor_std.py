import sys
import os
import unittest
from unittest import mock

# Ensure src/ is importable
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


class TestDockerMonitor(unittest.TestCase):
    def setUp(self):
        self.cfg = DummyConfig()
        self.fm = DummyFirewallManager()
        self.monitor = DockerMonitor(self.cfg, self.fm)
        # avoid real Docker client creation
        self.monitor.client = mock.MagicMock()
        self.monitor._get_service_custom_ports = mock.MagicMock(return_value=[])

    def test_extract_custom_firewall_ports_parsing(self):
        labels = {
            "docker-ipv6-firewall.ports": "809/tcp, 443:444/udp, 5000"
        }
        parsed = self.monitor._extract_custom_firewall_ports(labels)
        
        # Check parsed entries
        has_809 = any(p['external_port'] == 809 and p['internal_port'] == 809 and p['protocol'] == 'tcp' for p in parsed)
        has_443 = any(p['external_port'] == 443 and p['internal_port'] == 444 and p['protocol'] == 'udp' for p in parsed)
        has_5000 = any(p['external_port'] == 5000 and p['internal_port'] == 5000 for p in parsed) # Default protocol is usually tcp if not specified, check implementation
        
        self.assertTrue(has_809, "Should parse 809/tcp")
        self.assertTrue(has_443, "Should parse 443:444/udp")
        self.assertTrue(has_5000, "Should parse 5000")

    def test_derive_service_ports_from_containers_with_port_bindings(self):
        # Prepare two fake containers with port bindings and network ports
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
                    '443/tcp': [{'HostPort': '0', 'HostIp': ''}],  # no host binding -> should be IGNORED
                    '53/udp': [{'HostPort': '8053', 'HostIp': ''}]
                }
            }
        }

        # Mock client.containers.list
        fake_container1 = mock.MagicMock()
        fake_container2 = mock.MagicMock()
        self.monitor.client.containers.list.return_value = [fake_container1, fake_container2]

        # Monkeypatch _get_container_info
        infos = [container_info1, container_info2]
        def get_info_side_effect(container):
            return infos.pop(0)
        self.monitor._get_container_info = mock.MagicMock(side_effect=get_info_side_effect)

        derived = self.monitor._derive_service_ports_from_containers("dummy-service")
        
        sigs = {f"{p['protocol']}_{p['published_port']}_{p['target_port']}" for p in derived}
        self.assertIn("tcp_8080_80", sigs)
        self.assertIn("udp_8053_53", sigs)
        self.assertNotIn("tcp_443_443", sigs, "Unpublished port 443 should NOT be derived")

    def test_get_service_info_fallback_to_container_labels(self):
        # Simulate subprocess.run failing
        import subprocess
        self.monitor.client.containers.list.return_value = [mock.MagicMock()]
        
        self.monitor._get_container_info = mock.MagicMock(return_value={
            'config': {
                'Labels': {
                    'com.docker.swarm.service.id': 'svc-1234',
                    'com.docker.swarm.service.name': 'svc-name'
                }
            }
        })

        # patch subprocess.run to raise CalledProcessError
        with mock.patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, ['docker'])):
            svc_info = self.monitor._get_service_info('svc-name')

        self.assertIsNotNone(svc_info)
        self.assertEqual(svc_info['id'], 'svc-1234')
        self.assertEqual(svc_info['name'], 'svc-name')

    def test_derive_service_ports_exclusive_mode(self):
        """Test that if custom labels exist, native ports are ignored (Exclusive Mode)"""
        # Mock custom ports return
        self.monitor._get_service_custom_ports = mock.MagicMock(return_value=[{
            'internal_port': 8080, 
            'external_port': 5443, 
            'protocol': 'tcp', 
            'type': 'custom_firewall'
        }])

        # Should NOT call containers.list if custom ports exist (optimization)
        # OR if it does, it should ignore the result.
        # Implementation detail: we return early.
        
        derived = self.monitor._derive_service_ports_from_containers("exclusive-service")
        
        self.assertEqual(len(derived), 1)
        p = derived[0]
        self.assertEqual(p['published_port'], 5443)
        self.assertEqual(p['target_port'], 8080)
        self.assertEqual(p['publish_mode'], 'custom_label_exclusive')

if __name__ == '__main__':
    unittest.main()
