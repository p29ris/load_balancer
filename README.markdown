# ICS 4104: Distributed Systems - Load Balancer Assignment

## Overview
This project implements a customizable load balancer using consistent hashing to distribute client requests across multiple server containers. The system is built with Python (Flask), Docker, and a Docker network for communication. It supports dynamic scaling, failure recovery, and load distribution analysis.

## Design Choices
- **Language**: Python with Flask for simplicity and robust HTTP handling.
- **Consistent Hashing**: Implemented using a sorted list with linear probing for conflict resolution.
- **Docker**: Containers for servers and load balancer, managed via `docker-compose`.
- **Failure Detection**: Heartbeat checks every 5 seconds to detect and replace failed servers.
- **Hash Functions**: Used as specified: `H(i) = i + 2i + 2172` for requests, `Φ(i,j) = i + j + 2j + 25` for virtual servers.

## Assumptions
- Docker is installed and running on Parrot OS (Debian-based).
- Servers are stateless, handling only `/home` and `/heartbeat` endpoints.
- Random request IDs are used for hashing to simulate client requests.
- Hostnames are unique and randomly generated if not specified.

## Setup and Deployment
1. **Install Docker**:
   ```bash
   sudo apt-get update
   sudo apt-get install ca-certificates curl gnupg lsb-release
   sudo mkdir -p /etc/apt/keyrings
   curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
   echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
   sudo apt-get update
   sudo apt-get install docker-ce docker-ce-cli containerd.io docker-compose-plugin
   ```

2. **Clone Repository**:
   ```bash
   git clone <your-repo-url>
   cd load-balancer
   ```

3. **Build and Run**:
   ```bash
   make build
   make up
   ```

4. **Access Load Balancer**: Endpoints are available at `http://localhost:5000`.

## Testing
Run the test script to verify functionality:
```bash
make test
```

### Test Script
The test script (`tests/test_load_balancer.py`) sends 10,000 async requests, tests scaling, and simulates server failure.

<xaiArtifact artifact_id="23758470-6ccb-4db3-b5a6-ede6615746f5" artifact_version_id="7a3c2c3b-24de-4d9d-bce2-c9993e549cfe" title="tests/test_load_balancer.py" contentType="text/python">
import asyncio
import aiohttp
import matplotlib.pyplot as plt
import random
import json

async def send_request(session, url):
    async with session.get(url) as response:
        return await response.json()

async def test_load_distribution():
    async with aiohttp.ClientSession() as session:
        counts = {'server_1': 0, 'server_2': 0, 'server_3': 0}
        tasks = [send_request(session, 'http://localhost:5000/home') for _ in range(10000)]
        responses = await asyncio.gather(*tasks)
        for resp in responses:
            server = resp['message'].split(': ')[1]
            counts[server] = counts.get(server, 0) + 1
        
        plt.bar(counts.keys(), counts.values())
        plt.title('Request Distribution Across 3 Servers')
        plt.savefig('load_distribution.png')
        print("A-1: Request counts:", counts)

async def test_scaling():
    async with aiohttp.ClientSession() as session:
        loads = []
        for n in range(2, 7):
            # Add servers
            payload = {'n': n - 3, 'hostnames': [f'server_{i}' for i in range(4, n+1)]} if n > 3 else {'n': 0}
            async with session.post('http://localhost:5000/add', json=payload) as resp:
                pass
            counts = {}
            tasks = [send_request(session, 'http://localhost:5000/home') for _ in range(10000)]
            responses = await asyncio.gather(*tasks)
            for resp in responses:
                server = resp['message'].split(': ')[1]
                counts[server] = counts.get(server, 0) + 1
            avg_load = sum(counts.values()) / len(counts)
            loads.append(avg_load)
            # Reset to 3 servers
            if n > 3:
                async with session.delete('http://localhost:5000/rm', json={'n': n-3, 'hostnames': [f'server_{i}' for i in range(4, n+1)]}) as resp:
                    pass
        plt.plot(range(2, 7), loads)
        plt.title('Average Load vs Number of Servers')
        plt.savefig('scaling.png')
        print("A-2: Average loads:", loads)

async def test_failure_recovery():
    async with aiohttp.ClientSession() as session:
        # Simulate failure by stopping server_1
        import docker
        client = docker.from_env()
        client.containers.get('server_1').stop()
        await asyncio.sleep(10)  # Wait for replacement
        async with session.get('http://localhost:5000/rep') as resp:
            data = await resp.json()
            print("A-3: Replicas after failure:", data['message']['replicas'])

if __name__ == '__main__':
    asyncio.run(test_load_distribution())
    asyncio.run(test_scaling())
    asyncio.run(test_failure_recovery())