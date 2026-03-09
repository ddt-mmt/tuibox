#!/usr/bin/env python3
import requests, re, time, subprocess, sys
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from datetime import datetime

console = Console()

# --- CONFIG ---
# Harap ganti placeholder di bawah ini dengan kredensial Anda yang sebenarnya
ROUTER, PORT, USER, PASS = "10.0.0.110", "21112", "YOUR_ROUTER_USERNAME", "YOUR_ROUTER_PASSWORD"
URL, TOKEN = "http://10.28.1.100:8001/api", "YOUR_NETBOX_API_TOKEN"
HEADERS = {"Authorization": f"Token {TOKEN}", "Content-Type": "application/json"}
ALLOWED_PREFIXES = ["10.28.", "192.168.30.", "192.168.80."]

def cmd(command):
    f = f'sshpass -p "{PASS}" ssh -p {PORT} -o StrictHostKeyChecking=no {USER}@{ROUTER} "{command}"'
    return subprocess.run(f, shell=True, capture_output=True, text=True).stdout

def deep_sync():
    waktu_skrg = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    console.print(Panel(f"[bold cyan]TUIBOX DEEP SCAN & SYNC IPAM[/bold cyan]\n[white]Waktu: {waktu_skrg} | Mode: Anti-Device Hiding[/white]", expand=False))
    
    # 1. PROBING (Membangunkan Perangkat)
    with console.status("[bold yellow]Mengirim paket probe agresif (Ping Flood)...[/bold yellow]", spinner="dots"):
        for p in ALLOWED_PREFIXES:
            p_clean = p.rstrip('.')
            cmd(f":for i from=1 to=254 do={{ /tool ping {p_clean}.$i count=5 interval=100ms }}")
        time.sleep(20)

    # 2. HARVESTING (Tarik Data Router)
    with console.status("[bold yellow]Menarik data ARP & Interface dari Router...[/bold yellow]", spinner="dots"):
        arp_raw = cmd("/ip arp print detail without-paging")
        addr_raw = cmd("/ip address print detail without-paging")
        
        live_devices = {}
        # Menarik IP Gateway dari Interface agar tidak pernah hilang
        if_ips = re.findall(r"address=([\d\.]+)/(\d+)", addr_raw)
        for ip, mask in if_ips:
            if any(ip.startswith(p) for p in ALLOWED_PREFIXES):
                live_devices[ip] = "GATEWAY-IF"

        # Menarik IP Client dari ARP
        client_ips = re.findall(r"address=([\d\.]+) .*?mac-address=([A-F0-9:]+)", arp_raw)
        for ip, mac in client_ips:
            if any(ip.startswith(p) for p in ALLOWED_PREFIXES):
                live_devices[ip] = mac.upper()

    # 3. SYNC (Rekonsiliasi dengan NetBox)
    added, updated, preserved = 0, 0, 0
    with console.status(f"[bold yellow]Menyinkronkan {len(live_devices)} perangkat ke NetBox...[/bold yellow]", spinner="dots"):
        nb_res = requests.get(f"{URL}/ipam/ip-addresses/?limit=1000", headers=HEADERS).json()
        nb_ips = {item['address'].split('/')[0]: item['id'] for item in nb_res['results'] if any(item['address'].startswith(p) for p in ALLOWED_PREFIXES)}

        for ip, mac in live_devices.items():
            label = "OOB Ruijie" if "30." in ip else "ME Device" if "80." in ip else "Active Host"
            
            if ip in nb_ips:
                # Update data lama (Format /24). Label [NEW] akan hilang otomatis jika IP sudah di-update
                payload = {"address": f"{ip}/24", "status": "active", "description": f"{label} | MAC: {mac}"}
                requests.patch(f"{URL}/ipam/ip-addresses/{nb_ips[ip]}/", headers=HEADERS, json=payload)
                updated += 1
            else:
                # BUAT IP BARU DENGAN TAG [NEW]
                payload = {"address": f"{ip}/24", "status": "active", "description": f"[NEW] {label} | MAC: {mac}"}
                requests.post(f"{URL}/ipam/ip-addresses/", headers=HEADERS, json=payload)
                added += 1

        for ip_old in nb_ips.keys():
            if ip_old not in live_devices:
                preserved += 1 # IP tidak dihapus, hanya dibiarkan (Preserved)

    # 4. REPORTING (Akan tercetak rapi di file log Cronjob)
    table = Table(title="Laporan Deep Scan (NetBox vs Live)", show_header=True, header_style="bold magenta")
    table.add_column("Kategori Metrik", style="cyan")
    table.add_column("Jumlah", justify="right", style="green")
    
    table.add_row("Total IP Aktif (Live Router)", str(len(live_devices)))
    table.add_row("IP Baru Terdaftar [NEW]", str(added))
    table.add_row("IP Berhasil Diperbarui", str(updated))
    table.add_row("IP Sedang Tidur (Preserved)", str(preserved))
    
    console.print(table)
    console.print("[bold green]✔ Sinkronisasi Selesai![/bold green]\n")

if __name__ == "__main__":
    try:
        deep_sync()
    except KeyboardInterrupt:
        console.print("\n[bold red]❌ Dibatalkan oleh user (Ctrl+C).[/bold red]")
        sys.exit(0)
