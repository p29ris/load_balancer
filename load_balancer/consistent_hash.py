import random
import docker
import logging

class ConsistentHash:
    def __init__(self, num_slots=512, virtual_nodes=9):
        self.num_slots = num_slots
        self.virtual_nodes = virtual_nodes
        self.ring = []
        self.servers = {}
        self.client = docker.from_env()
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def _hash_request(self, i):
        return (i + 2 * i + 2172) % self.num_slots

    def _hash_server(self, i, j):
        return (i + j + 2 * j + 25) % self.num_slots

    def add_server(self, hostname):
        if hostname in self.servers:
            self.logger.warning(f"Server {hostname} already exists")
            return
        server_id = len(self.servers)
        self.servers[hostname] = []
        for j in range(self.virtual_nodes):
            slot = self._hash_server(server_id, j)
            # Linear probing for conflicts
            while any(s['slot'] == slot for s in self.ring):
                slot = (slot + 1) % self.num_slots
            self.ring.append({'slot': slot, 'hostname': hostname})
        self.ring.sort(key=lambda x: x['slot'])
        self.logger.info(f"Added server {hostname} with {self.virtual_nodes} virtual nodes")

    def remove_server(self, hostname):
        if hostname not in self.servers:
            self.logger.warning(f"Server {hostname} does not exist")
            return
        self.ring = [entry for entry in self.ring if entry['hostname'] != hostname]
        del self.servers[hostname]
        self.logger.info(f"Removed server {hostname}")

    def get_server(self, request_id):
        if not self.ring:
            return None
        slot = self._hash_request(request_id)
        for entry in self.ring:
            if entry['slot'] >= slot:
                return entry['hostname']
        return self.ring[0]['hostname']