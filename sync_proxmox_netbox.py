#!/usr/bin/env python3
import requests
import re
import subprocess
import os
import json
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

console = Console()

if os.path.exists('.env'):
    with open('.env') as f:
        for line in f:
            if '=' in line and not line.startswith(('#', '\n')):
                key, val = line.strip().split('=', 1)
                os.environ[key] = val

class ProxmoxNetboxSync:
    def __init__(self):
        self.host = os.getenv("PVE_HOST", "")
        self.user = os.getenv("PVE_USER", "root")
        self.password = os.getenv("PVE_PASS", "")
        self.nb_url = os.getenv("NETBOX_URL", "").replace('/api', '')
        self.nb_token = os.getenv("NETBOX_TOKEN", "")
        self.cluster_name = os.getenv("PVE_CLUSTER", "Proxmox-Cluster")
        self.headers = {"Authorization": f"Token {self.nb_token}", "Content-Type": "application/json"}

    def run_ssh(self, command):
        cmd_str = f'sshpass -p "{self.password}" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 {self.user}@{self.host} "{command}"'
        try:
            result = subprocess.run(cmd_str, shell=True, capture_output=True, text=True, timeout=30)
            return result.stdout if result.returncode == 0 else ""
        except: return ""

    def sync(self):
        console.print(Panel(f"[bold magenta]🚀 PROXMOX CLUSTER SYNC (V23 - PRECISION SPECS) 🚀\nCluster: {self.cluster_name}[/bold magenta]", expand=False))
        nb_api = f"{self.nb_url}/api"

        raw_resources = self.run_ssh("pvesh get /cluster/resources --output-format json")
        if not raw_resources: return console.print("[bold red]❌ Gagal koneksi ke Proxmox.[/bold red]")
        
        resources = [r for r in json.loads(raw_resources) if r['type'] in ['qemu', 'lxc']]

        cl_res = requests.get(f"{nb_api}/virtualization/clusters/?name={self.cluster_name}", headers=self.headers).json()
        cluster_id = cl_res['results'][0]['id'] if cl_res['count'] > 0 else None
        site_res = requests.get(f"{nb_api}/dcim/sites/?name=DC Cibinong", headers=self.headers).json()
        site_id = site_res['results'][0]['id'] if site_res['count'] > 0 else None

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TaskProgressColumn(), console=console) as progress:
            task = progress.add_task(f"[cyan]Syncing Specs {len(resources)} Resources...", total=len(resources))
            
            for res in resources:
                vmid, name, node, res_type = res['vmid'], res['name'], res['node'], res['type']
                nb_status = "active" if res['status'] == "running" else "offline"

                path_type = "qemu" if res_type == 'qemu' else "lxc"
                # Pakai --output-format json supaya datanya akurat dan gampang di-parse
                config_json = self.run_ssh(f"pvesh get /nodes/{node}/{path_type}/{vmid}/config --output-format json")
                
                vcpus = 1.0
                memory_mb = 1024
                disk_mb = 0
                config = {}

                if config_json:
                    try:
                        config = json.loads(config_json)
                        # --- LOGIKA vCPU ---
                        # VM pakai 'cores', LXC pakai 'cpus'
                        vcpus = float(config.get('cores', config.get('cpus', 1.0)))
                        
                        # --- LOGIKA RAM ---
                        raw_mem = int(config.get('memory', 1024))
                        # Jika angka di atas 1 Juta, Proxmox ngirim dalam satuan Bytes
                        if raw_mem > 1000000:
                            memory_mb = raw_mem // (1024 * 1024)
                        else:
                            memory_mb = raw_mem
                        
                        # --- LOGIKA DISK ---
                        # Iterasi semua key di config untuk cari drive (scsi, virtio, rootfs, dll)
                        for key, value in config.items():
                            if any(x in key for x in ['scsi', 'virtio', 'ide', 'sata', 'rootfs']):
                                size_match = re.search(r'size=(\d+\.?\d*)([GM])', str(value))
                                if size_match:
                                    val, unit = float(size_match.group(1)), size_match.group(2)
                                    disk_mb += (val * 1024) if unit == 'G' else val
                    except: pass

                # Sync to NetBox
                vm_check = requests.get(f"{nb_api}/virtualization/virtual-machines/?name={name}&cluster_id={cluster_id}", headers=self.headers).json()
                payload = {
                    "name": name, "cluster": cluster_id, "status": nb_status, "site": site_id,
                    "vcpus": vcpus, "memory": int(memory_mb), "disk": int(disk_mb),
                    "comments": f"Node: {node} | ID: {vmid} | Type: {res_type.upper()}"
                }

                if vm_check['count'] == 0:
                    vm_id = requests.post(f"{nb_api}/virtualization/virtual-machines/", headers=self.headers, json=payload).json()['id']
                else:
                    vm_id = vm_check['results'][0]['id']
                    requests.patch(f"{nb_api}/virtualization/virtual-machines/{vm_id}/", headers=self.headers, json=payload)

                # --- IP & Interface Mapping ---
                # Untuk MAC Address kita tetap pakai regex dari teks mentah karena lebih aman
                raw_cfg = str(config)
                macs = re.findall(r'([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})', raw_cfg)
                primary_ip_id = None

                for idx, mac in enumerate(macs):
                    mac = mac.upper()
                    if_name = f"net{idx}"
                    if_check = requests.get(f"{nb_api}/virtualization/interfaces/?virtual_machine_id={vm_id}&name={if_name}", headers=self.headers).json()
                    if if_check['count'] == 0:
                        if_id = requests.post(f"{nb_api}/virtualization/interfaces/", headers=self.headers, json={"virtual_machine": vm_id, "name": if_name, "mac_address": mac, "type": "virtual"}).json()['id']
                    else: if_id = if_check['results'][0]['id']

                    ip_search = requests.get(f"{nb_api}/ipam/ip-addresses/?q={mac}", headers=self.headers).json()
                    if ip_search['count'] > 0:
                        ip_id = ip_search['results'][0]['id']
                        requests.patch(f"{nb_api}/ipam/ip-addresses/{ip_id}/", headers=self.headers, json={"assigned_object_type": "virtualization.vminterface", "assigned_object_id": if_id})
                        primary_ip_id = ip_id

                if primary_ip_id:
                    requests.patch(f"{nb_api}/virtualization/virtual-machines/{vm_id}/", headers=self.headers, json={"primary_ip4": primary_ip_id})

                progress.advance(task)

        console.print(f"\n[bold green]✅ V23 DEPLOYED! vCPU & RAM harusnya sudah akurat sekarang Mas.[/bold green]")

if __name__ == "__main__":
    app = ProxmoxNetboxSync()
    app.sync()
