#!/usr/bin/env python3
import requests, re, subprocess, os, json, csv, io, base64, sys
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

console = Console()

# --- BACA KONFIGURASI (.env) ---
if os.path.exists('.env'):
    with open('.env') as f:
        for line in f:
            if '=' in line and not line.startswith(('#', '\n')):
                key, val = line.strip().split('=', 1)
                os.environ[key] = val
else:
    console.print(Panel("[bold red]🚨 ERROR: File konfigurasi (.env) tidak ditemukan![/bold red]\n\n[yellow]Silakan buat file '.env' di direktori yang sama dengan skrip ini.\nAnda bisa menyalin template dari '.env.example' (jika tersedia) atau membuatnya secara manual dengan variabel lingkungan yang diperlukan.[/yellow]\n\n[bold white]Skrip akan berhenti.[/bold white]", expand=False))
    sys.exit(1)

class HyperVNetboxSync:
    def __init__(self):
        self.host = os.getenv("HYPERV_HOST", "")
        self.user = os.getenv("HYPERV_USER", "Administrator")
        self.password = os.getenv("HYPERV_PASS", "")
        self.nb_url = os.getenv("NETBOX_URL", "").replace('/api', '')
        self.nb_token = os.getenv("NETBOX_TOKEN", "")
        self.cluster_name = os.getenv("HYPERV_CLUSTER", "HyperV-Cluster")
        self.headers = {"Authorization": f"Token {self.nb_token}", "Content-Type": "application/json"}

    def run_ssh_ps_encoded(self, ps_script):
        # Mengirim command dalam format Base64 agar karakter khusus PowerShell aman di CMD Windows
        blank_script = ps_script.encode('utf-16-le')
        base64_script = base64.b64encode(blank_script).decode('utf-8')
        
        cmd = f'sshpass -p "{self.password}" ssh -o StrictHostKeyChecking=no {self.user}@{self.host} "powershell -NoProfile -ExecutionPolicy Bypass -EncodedCommand {base64_script}"'
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=90)
            return result.stdout if result.returncode == 0 else ""
        except: return ""

    def sync(self):
        console.print(Panel(f"[bold green]🚀 HYPER-V OFFLINE-AWARE SYNC (V26) 🚀\nHost: {self.host}[/bold green]", expand=False))
        nb_api = f"{self.nb_url}/api"
        
        # 1. Pastikan Cluster & Site ada di NetBox
        site_res = requests.get(f"{nb_api}/dcim/sites/?name=DC Cibinong", headers=self.headers).json()
        site_id = site_res['results'][0]['id'] if site_res['count'] > 0 else None
        cl_res = requests.get(f"{nb_api}/virtualization/clusters/?name={self.cluster_name}", headers=self.headers).json()
        cluster_id = cl_res['results'][0]['id'] if cl_res['count'] > 0 else None

        # 2. PowerShell Script (Membaca Startup RAM & CPU biarpun VM Mati)
        ps_script = """
        $vms = Get-VM
        $results = foreach ($vm in $vms) {
            # Mengambil ukuran Hard Drive (VHD)
            try {
                $vhdSize = ($vm.HardDrives.Path | Get-VHD | Measure-Object -Property Size -Sum).Sum / 1MB
            } catch { $vhdSize = 0 }
            
            [PSCustomObject]@{
                Name     = $vm.Name
                State    = $vm.State.ToString()
                vCPUs    = $vm.ProcessorCount
                MemoryMB = [int]($vm.MemoryStartup / 1MB)
                DiskMB   = [int]$vhdSize
                MACs     = ($vm.NetworkAdapters.MacAddress -join ';')
            }
        }
        $results | ConvertTo-Csv -NoTypeInformation
        """
        
        vms_raw = self.run_ssh_ps_encoded(ps_script)
        
        if not vms_raw or "Name" not in vms_raw:
            console.print("[bold red]❌ Gagal narik data. Pastikan VM terdaftar di Hyper-V.[/bold red]")
            return

        f = io.StringIO(vms_raw.strip())
        reader = csv.DictReader(f)
        vm_list = list(reader)

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TaskProgressColumn(), console=console) as progress:
            task = progress.add_task(f"[cyan]Syncing {len(vm_list)} Hyper-V VMs...", total=len(vm_list))
            
            for vm in vm_list:
                name = vm['Name']
                # Status NetBox Mapping
                nb_status = "active" if vm['State'] == "Running" else "offline"
                
                # Spesifikasi (Tetap terisi walau VM Off)
                vcpus = float(vm['vCPUs']) if vm['vCPUs'] else 1.0
                memory_mb = int(vm['MemoryMB']) if vm['MemoryMB'] else 1024
                disk_mb = int(vm['DiskMB']) if vm['DiskMB'] else 0

                # --- SINKRONISASI VM ---
                vm_check = requests.get(f"{nb_api}/virtualization/virtual-machines/?name={name}&cluster_id={cluster_id}", headers=self.headers).json()
                payload = {
                    "name": name, "cluster": cluster_id, "status": nb_status, "site": site_id,
                    "vcpus": vcpus, "memory": memory_mb, "disk": disk_mb,
                    "comments": f"Hyper-V Host: {self.host} (Auto-Sync V26)"
                }

                if vm_check['count'] == 0:
                    vm_id = requests.post(f"{nb_api}/virtualization/virtual-machines/", headers=self.headers, json=payload).json()['id']
                else:
                    vm_id = vm_check['results'][0]['id']
                    requests.patch(f"{nb_api}/virtualization/virtual-machines/{vm_id}/", headers=self.headers, json=payload)

                # --- IP MAPPING (MAC) ---
                raw_macs = vm['MACs'].split(';')
                primary_ip_id = None
                
                for idx, mac in enumerate(raw_macs):
                    if not mac or mac == "000000000000": continue
                    # Format MAC: XXXXXXXXXXXX -> XX:XX:XX:XX:XX:XX
                    formatted_mac = ':'.join(mac[i:i+2] for i in range(0, 12, 2)).upper()
                    if_name = f"eth{idx}"
                    
                    if_check = requests.get(f"{nb_api}/virtualization/interfaces/?virtual_machine_id={vm_id}&name={if_name}", headers=self.headers).json()
                    if if_check['count'] == 0:
                        if_id = requests.post(f"{nb_api}/virtualization/interfaces/", headers=self.headers, json={"virtual_machine": vm_id, "name": if_name, "mac_address": formatted_mac, "type": "virtual"}).json()['id']
                    else: if_id = if_check['results'][0]['id']

                    # Cari IP di IPAM berdasarkan MAC (Tetap jalan walau VM mati)
                    ip_search = requests.get(f"{nb_api}/ipam/ip-addresses/?q={formatted_mac}", headers=self.headers).json()
                    if ip_search['count'] > 0:
                        ip_data = ip_search['results'][0]
                        requests.patch(f"{nb_api}/ipam/ip-addresses/{ip_data['id']}/", headers=self.headers, json={"assigned_object_type": "virtualization.vminterface", "assigned_object_id": if_id})
                        primary_ip_id = ip_data['id']

                if primary_ip_id:
                    requests.patch(f"{nb_api}/virtualization/virtual-machines/{vm_id}/", headers=self.headers, json={"primary_ip4": primary_ip_id})

                progress.advance(task)

        console.print(f"\n[bold green]✅ FIX SELESAI! VM Offline sekarang punya spek lengkap.[/bold green]")

if __name__ == "__main__":
    HyperVNetboxSync().sync()
