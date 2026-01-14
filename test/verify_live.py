
import sys
import os
import logging
import docker

import sys
import os
import logging
import docker

# Ensure src/ is importable relative to this script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(SCRIPT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from docker_monitor import DockerMonitor
from firewall_manager import FirewallManager

# Setup basic config
class Config:
    def __init__(self):
        self.docker_socket = "unix:///var/run/docker.sock"
        self.monitored_networks = ["bridge", "host", "macvlan"] # Monitor all typically
        self.ip6tables_cmd = "ip6tables"
        self.iptables_cmd = "iptables"
        self.chain_name = "DOCKER_IPV6_FORWARD"
        self.input_chain_name = "DOCKER_IPV6_INPUT"
        self.nat_chain_name = "DOCKER_IPV6_NAT"
        self.ipv4_chain_name = "DOCKER_IPV4_FORWARD"
        self.ipv4_nat_chain_name = "DOCKER_IPV4_NAT"
        self.parent_interface = "eth0"
        self.gateway_macvlan = "macvlan_gw"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LiveVerification")

def main():
    logger.info("Initializing Live Verification...")
    
    cfg = Config()
    fm = FirewallManager(cfg)
    monitor = DockerMonitor(cfg, fm)
    
    # Manually connect client (usually start() does this)
    monitor.client = docker.DockerClient(base_url=cfg.docker_socket)
    
    logger.info("--- Testing _get_local_services ---")
    services = monitor._get_local_services()
    logger.info(f"Found services via container labels: {services}")
    
    if not services:
        logger.warning("No swarm services found on this node. Testing might be limited.")
    
    for svc_name in services:
        logger.info(f"\nAnalyzing Service: {svc_name}")
        
        # 1. Test Fallback Service Info
        logger.info(f"  > Attempting _get_service_info (expecting fallback if no manager permissions)...")
        svc_info = monitor._get_service_info(svc_name)
        if svc_info:
            logger.info(f"    Result: ID={svc_info.get('id')}, Name={svc_info.get('name')}")
            if not svc_info.get('endpoint'):
                logger.info("    (Confirmed: Endpoint info missing, likely Fallback mode)")
        else:
            logger.error("    Failed to get service info.")

        # 2. Test Custom Ports (Label based)
        logger.info(f"  > Checking custom ports via _get_service_custom_ports...")
        custom = monitor._get_service_custom_ports(svc_name)
        logger.info(f"    Custom Ports found: {custom}")

        # 3. Test Derived Ports (Strict Mode Verification)
        logger.info(f"  > Deriving ports via _derive_service_ports_from_containers...")
        derived = monitor._derive_service_ports_from_containers(svc_name)
        logger.info(f"    Derived Ports: {derived}")
        
        # Validate Strictness
        # We can look at the actual container to see if there are exposed but unbound ports
        # and ensure they are NOT in 'derived'
        containers = monitor._get_service_containers(svc_name)
        # Note: _get_service_containers returns dicts, not objects. We need objects for inspection.
        # Let's manually inspect one container for the service
        raw_containers = monitor.client.containers.list(filters={'label': f'com.docker.swarm.service.name={svc_name}'})
        if raw_containers:
            c = raw_containers[0]
            c.reload()
            logger.info(f"    Inspecting container {c.name} for ground truth...")
            ports_setting = c.attrs['NetworkSettings']['Ports'] or {}
            logger.info(f"    Actual NetworkSettings.Ports: {ports_setting}")
            
            # Check for exposed but unbound ports
            for port_proto, bindings in ports_setting.items():
                is_bound = bindings and any(b.get('HostPort') for b in bindings)
                if not is_bound:
                    # Expect this NOT to be in Derived
                    proto = port_proto.split('/')[1]
                    port = int(port_proto.split('/')[0])
                    # Check if present in derived
                    found = any(d['target_port'] == port and d['protocol'] == proto for d in derived)
                    if found:
                        logger.error(f"    SECURITY FAILURE: Found unbound port {port}/{proto} in derived rules!")
                    else:
                        logger.info(f"    Security Check Passed: Unbound port {port}/{proto} correctly IGNORED.")
                else:
                    # Expect bound port to be present
                     proto = port_proto.split('/')[1]
                     port = int(port_proto.split('/')[0])
                     found = any(d['target_port'] == port and d['protocol'] == proto for d in derived)
                     if found:
                         logger.info(f"    Bound port {port}/{proto} correctly detected.")
                     else:
                         logger.warning(f"    Warning: Bound port {port}/{proto} NOT detected in derived rules (Check logic).")

if __name__ == "__main__":
    main()
