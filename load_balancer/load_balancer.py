from flask import Flask, jsonify, request
import docker
import random
import string
from consistent_hash import ConsistentHash
import requests
import logging
import time

app = Flask(__name__)
client = docker.from_env()
hash_map = ConsistentHash(num_slots=512, virtual_nodes=9)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize N=3 servers
def init_servers():
    network_name = 'lb_network'
    try:
        client.networks.get(network_name)
    except docker.errors.NotFound:
        client.networks.create(network_name, driver='bridge')
    
    for i in range(3):
        hostname = f"server_{i+1}"
        try:
            client.containers.get(hostname)
        except docker.errors.NotFound:
            container = client.containers.run(
                'server:latest',
                detach=True,
                name=hostname,
                network=network_name,
                environment=[f"SERVER_ID={i+1}"],
                ports={},
            )
            hash_map.add_server(hostname)
            logger.info(f"Started server {hostname}")

def check_heartbeat(hostname):
    try:
        response = requests.get(f"http://{hostname}:5000/heartbeat", timeout=2)
        return response.status_code == 200
    except requests.RequestException:
        return False

# Periodically check server health
def monitor_servers():
    while True:
        for hostname in list(hash_map.servers.keys()):
            if not check_heartbeat(hostname):
                logger.warning(f"Server {hostname} failed, removing and replacing")
                hash_map.remove_server(hostname)
                try:
                    client.containers.get(hostname).remove(force=True)
                except docker.errors.NotFound:
                    pass
                new_hostname = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
                client.containers.run(
                    'server:latest',
                    detach=True,
                    name=new_hostname,
                    network='lb_network',
                    environment=[f"SERVER_ID={new_hostname}"],
                )
                hash_map.add_server(new_hostname)
        time.sleep(5)

import threading
threading.Thread(target=monitor_servers, daemon=True).start()

@app.route('/rep', methods=['GET'])
def replicas():
    return jsonify({
        "message": {
            "N": len(hash_map.servers),
            "replicas": list(hash_map.servers.keys())
        },
        "status": " successful"
    }), 200

@app.route('/add', methods=['POST'])
def add_servers():
    data = request.get_json()
    n = data.get('n', 0)
    hostnames = data.get('hostnames', [])
    
    if len(hostnames) > n:
        return jsonify({
            "message": "Error: Length of hostname list is more than newly added instances",
            "status": "failure"
        }), 400
    
    network_name = 'lb_network'
    new_servers = []
    for i in range(n):
        hostname = hostnames[i] if i < len(hostnames) else ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        try:
            client.containers.get(hostname)
            continue
        except docker.errors.NotFound:
            container = client.containers.run(
                'server:latest',
                detach=True,
                name=hostname,
                network=network_name,
                environment=[f"SERVER_ID={hostname}"],
            )
            hash_map.add_server(hostname)
            new_servers.append(hostname)
    
    return jsonify({
        "message": {
            "N": len(hash_map.servers),
            "replicas": list(hash_map.servers.keys())
        },
        "status": "successful"
    }), 200

@app.route('/rm', methods=['DELETE'])
def remove_servers():
    data = request.get_json()
    n = data.get('n', 0)
    hostnames = data.get('hostnames', [])
    
    if len(hostnames) > n:
        return jsonify({
            "message": "Error: Length of hostname list is more than removable instances",
            "status": "failure"
        }), 400
    
    current_servers = list(hash_map.servers.keys())
    to_remove = hostnames[:]
    for i in range(n - len(hostnames)):
        available = [s for s in current_servers if s not in to_remove]
        if available:
            to_remove.append(random.choice(available))
    
    for hostname in to_remove:
        if hostname in hash_map.servers:
            hash_map.remove_server(hostname)
            try:
                client.containers.get(hostname).remove(force=True)
            except docker.errors.NotFound:
                pass
    
    return jsonify({
        "message": {
            "N": len(hash_map.servers),
            "replicas": list(hash_map.servers.keys())
        },
        "status": "successful"
    }), 200

@app.route('/<path:path>', methods=['GET'])
def route_request(path):
    request_id = random.randint(1, 1000000)  # Simulate request ID
    server = hash_map.get_server(request_id)
    if not server:
        return jsonify({
            "message": "No servers available",
            "status": "failure"
        }), 503
    
    try:
        response = requests.get(f"http://{server}:5000/{path}", timeout=2)
        return jsonify(response.json()), response.status_code
    except requests.RequestException:
        return jsonify({
            "message": f"Error: '{path}' endpoint does not exist in server replicas",
            "status": "failure"
        }), 400

if __name__ == '__main__':
    init_servers()
    app.run(host='0.0.0.0', port=5000)