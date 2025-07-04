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