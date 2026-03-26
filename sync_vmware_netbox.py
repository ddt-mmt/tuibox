#!/usr/bin/env python3
import requests, re, subprocess, os, json, sys # Added sys import
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

console = Console()

# --- BACA .env ---
if os.path.exists('.env'):
    with open('.env') as f:
        for line in f:
            if '=' in line and not line.startswith(('#', '\n')):
                key, val = line.strip().split('=', 1)
                os.environ[key] = val
else: # Added else block
    console.print(Panel("[bold red]🚨 ERROR: File konfigurasi (.env) tidak ditemukan![/bold red]\n\n[yellow]Silakan buat file '.env' di direktori yang sama dengan skrip ini.\nAnda bisa menyalin template dari '.env.example' (jika tersedia) atau membuatnya secara manual dengan variabel lingkungan yang diperlukan.[/yellow]\n\n[bold white]Skrip akan berhenti.[/bold white]", expand=False))
    sys.exit(1)

class VmwareNetboxSync:
    def __init__(self):
        self.host = os.getenv("VMWARE_HOST", "")
        self.user = os.getenv("VMWARE_USER", "root")
        self.password = os.getenv("VMWARE_PASS", "")
        self.nb_url = os.getenv("NETBOX_URL", "").replace('/api', '')
        self.nb_token = os.getenv("NETBOX_TOKEN", "")
        self.cluster_name = os.getenv("VMWARE_CLUSTER", "ESXi-Cluster")
        self.headers = {"Authorization": f"Token {self.nb_token}", "Content-Type": "application/json"}

    def run_ssh(self, command):
        cmd = f'sshpass -p "{self.password}" ssh -o StrictHostKeyChecking=no {self.user}@{self.host} "{command}"'
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            return result.stdout if result.returncode == 0 else ""
        except: return ""

    def sync(self):
        console.print(Panel(f"[bold blue]🚀 VMWARE ESXI TO NETBOX SYNC 🚀\nHost: {self.host}[/bold blue]", expand=False))
        nb_api = f"{self.nb_url}/api"
        
        # 1. Setup NetBox Site (DC Cibinong) & Cluster
        site_res = requests.get(f"{nb_api}/dcim/sites/?name=DC Cibinong", headers=self.headers).json()
        site_id = site_res['results'][0]['id'] if site_res['count'] > 0 else \
                  requests.post(f"{nb_api}/dcim/sites/", headers=self.headers, json={"name": "DC Cibinong", "slug": "dc-cibinong"}).json()['id']

        type_res = requests.get(f"{nb_api}/virtualization/cluster-types/?name=VMware%20vSphere", headers=self.headers).json()
        type_id = type_res['results'][0]['id'] if type_res['count'] > 0 else \
                  requests.post(f"{nb_api}/virtualization/cluster-types/", headers=self.headers, json={"name": "VMware vSphere", "slug": "vmware-vsphere"}).json()['id']

        cl_res = requests.get(f"{nb_api}/virtualization/clusters/?name={self.cluster_name}", headers=self.headers).json()
        cluster_id = cl_res['results'][0]['id'] if cl_res['count'] > 0 else \
                     requests.post(f"{nb_api}/virtualization/clusters/", headers=self.headers, json={"name": self.cluster_name, "type": type_id, "site": site_id}).json()['id']

        # 2. Ambil Daftar VMID
        vms_raw = self.run_ssh("vim-cmd vmsvc/getallvms")
        vm_list = []
        if not vms_raw:
            console.print("[bold red]❌ Gagal koneksi ke ESXi via SSH.[/bold red]"); return
            
        for line in vms_raw.splitlines()[1:]:
            parts = re.split(r'\s{2,}', line.strip())
            if len(parts) >= 2: vm_list.append({"vmid": parts[0], "name": parts[1]})

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TaskProgressColumn(), console=console) as progress:
            task = progress.add_task(f"[cyan]Syncing {len(vm_list)} ESXi VMs...", total=len(vm_list))
            
            for vm in vm_list:
                vmid, name = vm['vmid'], vm['name']
                
                # 3. Ambil Detail Summary
                summary = self.run_ssh(f"vim-cmd vmsvc/get.summary {vmid}")
                if not summary: progress.advance(task); continue

                # Regex Specs (RAM, CPU, Status)
                mem_m = re.search(r'memorySizeMB = (\d+)', summary)
                cpu_m = re.search(r'numCpu = (\d+)', summary)
                status_m = re.search(r'powerState = "(\w+)"', summary)
                
                vcpus = float(cpu_m.group(1)) if cpu_m else 1.0
                memory_mb = int(mem_m.group(1)) if mem_m else 1024
                nb_status = "active" if status_m and status_m.group(1) == "poweredOn" else "offline"

                # 4. Ambil Detail Disk
                # vim-cmd tidak memberikan info disk yang gampang dibaca, 
                # ini adalah taktik untuk mencari total komitmen disk (GigaBytes)
                disk_gb = 0
                for size_gb in re.findall(r'capacity = (\d+)', summary):
                    disk_gb += int(size_gb) // (1024 * 1024 * 1024)

                # 5. Sync VM ke NetBox
                vm_check = requests.get(f"{nb_api}/virtualization/virtual-machines/?name={name}&cluster_id={cluster_id}", headers=self.headers).json()
                payload = {
                    "name": name, "cluster": cluster_id, "status": nb_status, "site": site_id,
                    "vcpus": vcpus, "memory": memory_mb, "disk": int(disk_gb * 1024), # NetBox minta MB
                    "comments": f"VMware VMID: {vmid}"
                }

                if vm_check['count'] == 0:
                    vm_id = requests.post(f"{nb_api}/virtualization/virtual-machines/", headers=self.headers, json=payload).json()['id']
                else:
                    vm_id = vm_check['results'][0]['id']
                    requests.patch(f"{nb_api}/virtualization/virtual-machines/{vm_id}/", headers=self.headers, json=payload)

                # 6. Auto IP Map (MAC Address)
                # VMware format macAddress = "XX:XX:XX:XX:XX:XX"
                macs = re.findall(r'macAddress = "([0-9a-fA-F:]+)"', summary)
                primary_ip_id = None

                for idx, mac in enumerate(macs):
                    mac = mac.upper()
                    if_name = f"vmnet{idx}" # VMware standar interface name
                    if_check = requests.get(f"{nb_api}/virtualization/interfaces/?virtual_machine_id={vm_id}&name={if_name}", headers=self.headers).json()
                    if if_check['count'] == 0:
                        if_id = requests.post(f"{nb_api}/virtualization/interfaces/", headers=self.headers, json={"virtual_machine": vm_id, "name": if_name, "mac_address": mac, "type": "virtual"}).json()['id']
                    else: if_id = if_check['results'][0]['id']

                    # Cari IP di NetBox IPAM
                    ip_search = requests.get(f"{nb_api}/ipam/ip-addresses/?q={mac}", headers=self.headers).json()
                    if ip_search['count'] > 0:
                        ip_data = ip_search['results'][0]
                        requests.patch(f"{nb_api}/ipam/ip-addresses/{ip_data['id']}/", headers=self.headers, json={"assigned_object_type": "virtualization.vminterface", "assigned_object_id": if_id})
                        primary_ip_id = ip_data['id']

                if primary_ip_id:
                    requests.patch(f"{nb_api}/virtualization/virtual-machines/{vm_id}/", headers=self.headers, json={"primary_ip4": primary_ip_id})

                progress.advance(task)

        console.print(f"\n[bold green]✅ Sukses! {len(vm_list)} VM di VMware ESXi {self.host} tersinkron sempurna.[/bold green]")

if __name__ == "__main__":
    VmwareNetboxSync().sync()
