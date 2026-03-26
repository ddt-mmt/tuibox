#!/usr/bin/env python3
import os
import time
import importlib.util
import sys
from rich.console import Console
from rich.panel import Panel

console = Console()

# --- BACA BRANKAS RAHASIA (.env) ---
if os.path.exists('.env'):
    with open('.env') as f:
        for line in f:
            if '=' in line and not line.startswith(('#', '\n')):
                key, val = line.strip().split('=', 1)
                os.environ[key] = val

def load_module_from_file(module_name, file_path):
    """Fungsi ajaib untuk meng-import file python tanpa ekstensi .py (seperti tuibox)"""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def run_sync_all():
    console.print(Panel("[bold magenta]🚀 MENJALANKAN SINKRONISASI GLOBAL (IPAM & KVM) 🚀[/bold magenta]", expand=False))
    
    nb_url = os.getenv("NETBOX_URL", "http://10.28.1.100:8001/api")
    nb_token = os.getenv("NETBOX_TOKEN", "")
    
    headers = {
        "Authorization": f"Token {nb_token}", 
        "Content-Type": "application/json", 
        "Accept": "application/json"
    }

    # ==========================================
    # 1. RUN MIKROTIK IPAM SYNC
    # ==========================================
    console.print("\n[bold cyan]--- [1/2] Sinkronisasi Jaringan & IPAM (MikroTik) ---[/bold cyan]")
    try:
        # Import script tuibox
        tuibox_mod = load_module_from_file("tuibox", "./tuibox")
        mt_sync = tuibox_mod.TuiBoxSync()
        
        # Bypass setup() (Suntik variabel manual dari .env)
        mt_sync.router = os.getenv("MIKROTIK_IP", "10.0.2.110")
        mt_sync.port = int(os.getenv("MIKROTIK_PORT", "21112"))
        mt_sync.user = os.getenv("MIKROTIK_USER", "test-speed")
        mt_sync.password = os.getenv("MIKROTIK_PASS", "")
        mt_sync.nb_url = nb_url
        mt_sync.nb_token = nb_token
        
        raw_prefixes = os.getenv("PREFIXES", "10.28.0.0/16,192.168.30.0/24")
        mt_sync.prefixes_input = [p.strip() for p in raw_prefixes.split(',')]
        
        mt_sync.ping_sweep = False  # Sengaja dimatikan agar auto-sync berjalan cepat
        mt_sync.auto_sync = False   # Jalankan sekali jalan saja
        mt_sync.headers = headers
        
        if mt_sync.validate_connection():
            mt_sync.scan_and_sync()
    except Exception as e:
        console.print(f"[bold red]❌ Gagal menjalankan TUIBOX MikroTik: {e}[/bold red]")

    # ==========================================
    # 2. RUN KVM VM SYNC (WITH AUTO-IP)
    # ==========================================
    console.print("\n[bold cyan]--- [2/2] Sinkronisasi Virtual Machine (Red Hat KVM) ---[/bold cyan]")
    try:
        # Import script KVM
        import sync_kvm_netbox
        kvm_sync = sync_kvm_netbox.KvmNetboxSync()
        
        # Bypass setup() (Suntik variabel manual dari .env)
        kvm_sync.host = os.getenv("KVM_HOST", "10.28.14.87")
        kvm_sync.port = int(os.getenv("KVM_PORT", "22"))
        kvm_sync.user = os.getenv("KVM_USER", "root")
        kvm_sync.password = os.getenv("KVM_PASS", "")
        kvm_sync.nb_url = nb_url
        kvm_sync.nb_token = nb_token
        kvm_sync.cluster_name = os.getenv("KVM_CLUSTER", "vm-keruing03")
        kvm_sync.headers = headers
        
        # Jalankan pengecekan jika dirasa perlu, atau langsung eksekusi
        kvm_sync.sync_vms()
    except Exception as e:
        console.print(f"[bold red]❌ Gagal menjalankan KVM Sync: {e}[/bold red]")

    console.print("\n[bold green]✅ SEMUA SINKRONISASI SELESAI DENGAN SUKSES![/bold green]")

if __name__ == "__main__":
    start_time = time.time()
    run_sync_all()
    end_time = time.time()
    console.print(f"[dim]Waktu eksekusi total: {round(end_time - start_time, 2)} detik[/dim]\n")
