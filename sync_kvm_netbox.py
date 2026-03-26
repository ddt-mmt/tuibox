#!/usr/bin/env python3
import requests
import re
import subprocess
import getpass
import sys
import os

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

console = Console()

# --- BACA BRANKAS RAHASIA (.env) ---
if os.path.exists('.env'):
    with open('.env') as f:
        for line in f:
            if '=' in line and not line.startswith(('#', '\n')):
                key, val = line.strip().split('=', 1)
                os.environ[key] = val
else:
    console.print(Panel("[bold red]🚨 ERROR: File konfigurasi (.env) tidak ditemukan![/bold red]\n\n[yellow]Silakan buat file '.env' di direktori yang sama dengan skrip ini.\nAnda bisa menyalin template dari '.env.example' (jika tersedia) atau membuatnya secara manual dengan variabel lingkungan yang diperlukan.[/yellow]\n\n[bold white]Skrip akan berhenti.[/bold white]", expand=False))
    sys.exit(1)

class KvmNetboxSync:
    def __init__(self):
        self.host = ""
        self.port = 22
        self.user = ""
        self.password = ""
        self.nb_url = ""
        self.nb_token = ""
        self.cluster_name = "KVM-Keruing03"
        self.headers = {}

    def setup(self):
        console.print(Panel("[bold blue]🌟 TUIBOX: KVM to NetBox VM Sync (V16 - PERFECT SPECS) 🌟[/bold blue]", expand=False))

        def_host = os.getenv("KVM_HOST", "127.0.0.1")
        def_user = os.getenv("KVM_USER", "root")
        def_nb_url = os.getenv("NETBOX_URL", "http://localhost:8001/api")
        def_nb_token = os.getenv("NETBOX_TOKEN", "")

        self.host = input(f"🌐 IP Server KVM ({def_host}): ").strip() or def_host
        self.port = input("🔌 Port SSH (Default 22): ").strip() or "22"
        self.user = input(f"👤 Username ({def_user}): ").strip() or def_user
        self.password = getpass.getpass("🔑 Password (Hidden): ")

        self.nb_url = input(f"🔗 URL NetBox ({def_nb_url}): ").strip() or def_nb_url
        
        if def_nb_token:
            use_env_token = input("🎫 Gunakan API Token dari .env? [Y/n]: ").strip().lower()
            if use_env_token == 'n':
                self.nb_token = getpass.getpass("🎫 Masukkan API Token Baru (Hidden): ").strip()
            else:
                self.nb_token = def_nb_token
        else:
            self.nb_token = getpass.getpass("🎫 API Token (Hidden): ").strip()

        self.cluster_name = input("🏢 Nama Cluster di NetBox (ex: vm-keruing03): ").strip() or "vm-keruing03"

        self.headers = {
            "Authorization": f"Token {self.nb_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def run_ssh(self, command):
        cmd_str = f'sshpass -p "{self.password}" ssh -p {self.port} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=15 {self.user}@{self.host} "{command}"'
        try:
            result = subprocess.run(cmd_str, shell=True, capture_output=True, text=True, timeout=30)
            return result.stdout if result.returncode == 0 else ""
        except:
            return ""

    def get_or_create_cluster(self):
        type_res = requests.get(f"{self.nb_url}/virtualization/cluster-types/?name=KVM", headers=self.headers).json()
        if type_res.get('count', 0) == 0:
            type_id = requests.post(f"{self.nb_url}/virtualization/cluster-types/", headers=self.headers, json={"name": "KVM", "slug": "kvm"}).json()['id']
        else:
            type_id = type_res['results'][0]['id']

        cl_res = requests.get(f"{self.nb_url}/virtualization/clusters/?name={self.cluster_name}", headers=self.headers).json()
        if cl_res.get('count', 0) == 0:
            payload = {"name": self.cluster_name, "type": type_id}
            return requests.post(f"{self.nb_url}/virtualization/clusters/", headers=self.headers, json=payload).json()['id']
        return cl_res['results'][0]['id']

    def sync_vms(self):
        console.print("\n[bold yellow]1. Mengambil daftar VM dari Server...[/bold yellow]")
        raw_list = self.run_ssh("virsh list --all")

        if not raw_list or "Name" not in raw_list:
            console.print("[bold red]❌ Gagal mengambil data via SSH. Pastikan sshpass terinstall dan password benar.[/bold red]")
            return

        vm_list = []
        for line in raw_list.splitlines():
            line = line.strip()
            if not line or "---" in line or " Id " in line: continue

            m = re.match(r'^\s*([-\d]+)\s+(.+?)\s{2,}([a-zA-Z\s]+)$', line)
            if m:
                vm_list.append({"name": m.group(2).strip(), "status": m.group(3).strip().lower()})

        console.print(f"[bold green]✔ Berhasil! Ditemukan {len(vm_list)} VM di {self.host}[/bold green]")
        cluster_id = self.get_or_create_cluster()

        added, updated, ip_mapped = 0, 0, 0
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TaskProgressColumn(), console=console) as progress:
            task = progress.add_task("[cyan]Menganalisa CPU, RAM, Disk & Auto-Mapping IP...", total=len(vm_list))

            for vm in vm_list:
                vm_name = vm['name']
                nb_status = "active" if "running" in vm['status'] else "offline"

                dominfo = self.run_ssh(f"virsh dominfo '{vm_name}'")
                cpu_m = re.search(r'CPU\(s\):\s+(\d+)', dominfo)
                # FIX MEMORY: Hapus batasan "kB" agar match dengan semua output KVM
                mem_m = re.search(r'Max memory:\s+(\d+)', dominfo)

                vcpus = float(cpu_m.group(1)) if cpu_m else 1.0
                memory_mb = int(mem_m.group(1)) // 1024 if mem_m else 1024

                # FIX DISK: Ubah kalkulasi ke Megabytes (MB)
                disk_mb = 0
                blklist = self.run_ssh(f"virsh domblklist '{vm_name}'")
                for blk_line in blklist.splitlines():
                    if "Target" in blk_line or "---" in blk_line or not blk_line.strip(): continue
                    parts = blk_line.split()
                    if len(parts) >= 1:
                        target = parts[0]
                        blkinfo = self.run_ssh(f"virsh domblkinfo '{vm_name}' {target}")
                        cap_m = re.search(r'Capacity:\s+(\d+)', blkinfo)
                        # NetBox API meminta ukuran Disk dalam Megabytes (MB)
                        if cap_m: disk_mb += int(cap_m.group(1)) // (1024**2) 

                vm_check = requests.get(f"{self.nb_url}/virtualization/virtual-machines/?name={vm_name}&cluster_id={cluster_id}", headers=self.headers).json()
                vm_payload = {"name": vm_name, "cluster": cluster_id, "status": nb_status, "vcpus": vcpus, "memory": memory_mb}
                if disk_mb > 0: vm_payload["disk"] = disk_mb

                if vm_check['count'] == 0:
                    res_vm = requests.post(f"{self.nb_url}/virtualization/virtual-machines/", headers=self.headers, json=vm_payload).json()
                    vm_id = res_vm['id']
                    added += 1
                else:
                    vm_id = vm_check['results'][0]['id']
                    requests.patch(f"{self.nb_url}/virtualization/virtual-machines/{vm_id}/", headers=self.headers, json=vm_payload)
                    updated += 1

                # 3. Sync Interface & AUTO-MAP IP
                domif = self.run_ssh(f"virsh domiflist '{vm_name}'")
                macs = re.findall(r'([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})', domif)
                primary_ip_id = None

                for idx, mac in enumerate(macs):
                    mac = mac.upper()
                    iface_name = f"eth{idx}"

                    if_check = requests.get(f"{self.nb_url}/virtualization/interfaces/?virtual_machine_id={vm_id}&name={iface_name}", headers=self.headers).json()
                    if if_check['count'] == 0:
                        iface_id = requests.post(f"{self.nb_url}/virtualization/interfaces/", headers=self.headers, json={
                            "virtual_machine": vm_id, "name": iface_name, "mac_address": mac
                        }).json()['id']
                    else:
                        iface_id = if_check['results'][0]['id']

                    ip_search = requests.get(f"{self.nb_url}/ipam/ip-addresses/?q={mac}", headers=self.headers).json()
                    if ip_search['count'] > 0:
                        ip_data = ip_search['results'][0]
                        ip_id = ip_data['id']
                        
                        if not ip_data.get('assigned_object_id') == iface_id:
                            requests.patch(f"{self.nb_url}/ipam/ip-addresses/{ip_id}/", headers=self.headers, json={
                                "assigned_object_type": "virtualization.vminterface",
                                "assigned_object_id": iface_id
                            })

                        primary_ip_id = ip_id

                if primary_ip_id:
                    requests.patch(f"{self.nb_url}/virtualization/virtual-machines/{vm_id}/", headers=self.headers, json={
                        "primary_ip4": primary_ip_id
                    })

                progress.advance(task)

        console.print(f"\n[bold green]✨ Selesai! Baru: {added}, Update: {updated}, IP Otomatis Tertempel: {ip_mapped}[/bold green]")

if __name__ == "__main__":
    app = KvmNetboxSync()
    app.setup()
    app.sync_vms()
