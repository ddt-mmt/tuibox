#!/usr/bin/env python3
import pynetbox
from netmiko import ConnectHandler
import re
import getpass
import sys
import os
from rich.console import Console
from rich.panel import Panel

console = Console()

# ==========================================
# BACA BRANKAS RAHASIA (.env)
# ==========================================
if os.path.exists('.env'):
    with open('.env') as f:
        for line in f:
            if '=' in line and not line.startswith(('#', '\n')):
                key, val = line.strip().split('=', 1)
                os.environ[key] = val

console.print("\n🌟 NETBOX ALL-IN-ONE SYNC TOOL (SWITCH/ROUTER EDITION) 🌟")
print("------------------------------------------------------------")

# Ambil URL dan Token dari .env (Otomatis hapus '/api' di ujung jika ada)
env_url = os.getenv("NETBOX_URL", "http://10.28.1.100:8001")
NETBOX_URL = env_url[:-4] if env_url.endswith('/api') else env_url
NETBOX_TOKEN = os.getenv("NETBOX_TOKEN", "")

if not NETBOX_TOKEN:
    NETBOX_TOKEN = getpass.getpass("🎫 API Token NetBox tidak ditemukan di .env! Masukkan manual (Hidden): ").strip()

try:
    nb = pynetbox.api(NETBOX_URL, token=NETBOX_TOKEN)
except Exception as e:
    sys.exit(f"❌ Gagal koneksi ke NetBox API: {e}")

def make_slug(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')

vendors = {
    "1":  {"name": "Ruijie (SSH)", "driver": "ruijie_os"},
    "1t": {"name": "Ruijie (Telnet)", "driver": "ruijie_os_telnet"},
    "2":  {"name": "HPE (Comware)", "driver": "hp_comware"},
    "3":  {"name": "Cisco (IOS/XE)", "driver": "cisco_ios"},
    "4":  {"name": "Aruba (AOS-S)", "driver": "aruba_os"},
    "5":  {"name": "EdgeCore", "driver": "edgecore_es"},
    "6":  {"name": "Juniper (Junos)", "driver": "juniper_junos"},
    "7":  {"name": "Mikrotik", "driver": "mikrotik_routeros"},
    "8":  {"name": "BDCOM", "driver": "cisco_ios"},
}

for k, v in vendors.items():
    print(f"{k}. {v['name']}")

choice = input("\n👉 Pilih Vendor: ").strip()
if choice not in vendors: sys.exit("❌ Pilihan tidak valid.")
v_data = vendors[choice]

try:
    # --- INPUT IP TANPA PREFIX (Integrasi TUIBOX) ---
    IP_ADDR = input(f"🌐 Masukkan IP {v_data['name']} (ex: 10.28.3.107): ").strip()
    if not IP_ADDR: sys.exit("❌ IP tidak boleh kosong.")
    
    print(f"🔍 Mencari data IP {IP_ADDR} di NetBox IPAM...")
    nb_ip_check = nb.ipam.ip_addresses.get(address=IP_ADDR)
    IP_FULL = nb_ip_check.address if nb_ip_check else f"{IP_ADDR}/24"
    if nb_ip_check: print(f"✅ Ditemukan! Menggunakan prefix: {IP_FULL}")
    
    SSH_PORT = input(f"🔌 Port (Default {'23' if 'telnet' in v_data['driver'] else '22'}): ").strip()
    SSH_PORT = int(SSH_PORT) if SSH_PORT else (23 if "telnet" in v_data['driver'] else 22)
    TARGET_NAME = input("📝 Nama Perangkat di NetBox: ").strip()
    USER = input("👤 Username: ").strip()
    PASS = getpass.getpass("🔑 Password: ")

    device_cfg = {'device_type': v_data['driver'], 'host': IP_ADDR, 'username': USER, 'password': PASS, 'port': SSH_PORT, 'global_delay_factor': 2}
    print(f"\n🔄 Menghubungi {v_data['name']} {IP_ADDR}...")
    net_connect = ConnectHandler(**device_cfg)
    
    serial_number = ""
    model = "Generic-Model"
    ports_data = [] # {name, status, desc, type}
    l3_data = []    # {name, ip}

    # ======================================================
    # BLOK 1: ARUBA (DEEP CONFIG PARSER)
    # ======================================================
    if choice == "4":
        sh_ru = net_connect.send_command("show running-config")
        sh_inv = net_connect.send_command("show inventory")
        sh_status = net_connect.send_command("show interfaces status")
        sn_m = re.search(r'Serial Number\s+:\s+(\S+)', sh_inv)
        serial_number = sn_m.group(1) if sn_m else ""
        mod_m = re.search(r'module 1 type (\S+)', sh_ru)
        model = mod_m.group(1).upper() if mod_m else "Aruba-Switch"
        desc_map = {p: n for p, n in re.findall(r'interface (\d+)\s+name "(.*?)"', sh_ru, re.DOTALL)}
        for line in sh_status.splitlines():
            p_m = re.match(r'^(\d+)\s+', line.strip())
            if p_m:
                p_n = p_m.group(1); is_up = "Up" in line
                ports_data.append({'name': p_n, 'status': is_up, 'desc': desc_map.get(p_n, ""), 'type': '10gbase-x-sfpp' if int(p_n) > 24 else '1000base-t'})
        for v_id, v_name, v_body in re.findall(r'vlan (\d+)\s+name "(.*?)"(.*?)exit', sh_ru, re.DOTALL):
            ip_m = re.search(r'ip address ([0-9\.]+)', v_body)
            if ip_m: l3_data.append({'name': f"VLAN{v_id}", 'ip': ip_m.group(1)})

    # ======================================================
    # BLOK 2: RUIJIE (DEEP LOGS)
    # ======================================================
    elif "1" in choice:
        sh_ver = net_connect.send_command("show version")
        sh_status = net_connect.send_command("show interfaces status")
        sh_desc = net_connect.send_command("show interfaces description")
        sh_ip = net_connect.send_command("show ip interface brief")
        sn_m = re.search(r'(?:SN|Serial Number)\s*:\s*(\S+)', sh_ver, re.IGNORECASE)
        serial_number = sn_m.group(1) if sn_m else ""; mod_m = re.search(r'Ruijie\s+([A-Za-z0-9\-]+)', sh_ver)
        model = mod_m.group(1) if mod_m else "Ruijie-Switch"
        desc_map = {m.group(1): m.group(2).strip() for m in [re.match(r'^(\S+)\s+(?:up|down|adm)\s+(?:up|down|adm)\s+(.*)', l, re.IGNORECASE) for l in sh_desc.splitlines()] if m}
        for line in sh_status.splitlines():
            m = re.match(r'^(\S+)\s+(up|down|admin down)', line.strip(), re.IGNORECASE)
            if m: ports_data.append({'name': m.group(1), 'status': m.group(2).lower() == 'up', 'desc': desc_map.get(m.group(1), ""), 'type': 'other'})
        for line in sh_ip.splitlines():
            ip_m = re.search(r'^(VLAN\s*\d+)\s+([0-9\.]+)', line, re.IGNORECASE)
            if ip_m: l3_data.append({'name': ip_m.group(1).replace(" ", ""), 'ip': ip_m.group(2)})

    # ======================================================
    # BLOK 3: HPE (COMWARE SCAN)
    # ======================================================
    elif choice == "2":
        sh_ver = net_connect.send_command("display version")
        sh_manu = net_connect.send_command("display device manuinfo")
        sh_int_b = net_connect.send_command("display interface brief")
        sh_ip = net_connect.send_command("display ip interface brief")
        sn_m = re.search(r'DEVICE_SERIAL_NUMBER\s*:\s*(\S+)', sh_manu)
        serial_number = sn_m.group(1) if sn_m else ""; mod_m = re.search(r'HPE\s+([A-Za-z0-9\- ]+Switch)', sh_ver)
        model = mod_m.group(1).strip() if mod_m else "HPE-Switch"
        for line in sh_int_b.splitlines():
            m = re.match(r'^([A-Za-z0-9\-\/]+)\s+(UP|DOWN|ADM)', line.strip(), re.IGNORECASE)
            if m: ports_data.append({'name': m.group(1), 'status': m.group(2) == 'UP', 'desc': "", 'type': 'other'})
        for line in sh_ip.splitlines():
            ip_m = re.search(r'^(Vlan\S+)\s+([0-9\.]+)', line, re.IGNORECASE)
            if ip_m: l3_data.append({'name': ip_m.group(1), 'ip': ip_m.group(2)})

    # ======================================================
    # BLOK 4: CISCO & BDCOM
    # ======================================================
    elif choice in ["3", "8"]:
        sh_ver = net_connect.send_command("show version")
        sh_status = net_connect.send_command("show interfaces status")
        sh_ip = net_connect.send_command("show ip interface brief")
        sn_m = re.search(r'Processor board ID\s+(\S+)', sh_ver)
        serial_number = sn_m.group(1) if sn_m else ""; mod_m = re.search(r'[Cc]isco\s+(\S+)\s+processor', sh_ver)
        model = mod_m.group(1) if mod_m else "Cisco-Switch"
        for line in sh_status.splitlines():
            if "---" in line or "Port" in line or not line: continue
            parts = line.split()
            if len(parts) >= 2:
                p_n = parts[0]; is_up = "connected" in line.lower()
                ports_data.append({'name': p_n, 'status': is_up, 'desc': "", 'type': 'other'})
        for line in sh_ip.splitlines():
            ip_m = re.search(r'^(Vlan\d+)\s+([0-9\.]+)', line)
            if ip_m: l3_data.append({'name': ip_m.group(1), 'ip': ip_m.group(2)})

    # ======================================================
    # BLOK 5: MIKROTIK
    # ======================================================
    elif choice == "7":
        sh_res = net_connect.send_command("/system resource print")
        sh_sn = net_connect.send_command("/system routerboard print")
        sh_int = net_connect.send_command("/interface print detail without-paging")
        sh_ip = net_connect.send_command("/ip address print without-paging")
        sn_m = re.search(r'serial-number:\s+(\S+)', sh_sn); serial_number = sn_m.group(1) if sn_m else ""
        mod_m = re.search(r'board-name:\s+(.*)', sh_res); model = mod_m.group(1).strip() if mod_m else "MikroTik"
        for line in sh_int.splitlines():
            m = re.search(r'name="([^"]+)"\s+.*running=(\S+)', line)
            if m: ports_data.append({'name': m.group(1), 'status': m.group(2) == "true", 'desc': "", 'type': 'other'})
        for line in sh_ip.splitlines():
            ip_m = re.search(r'([0-9\.]+)/\d+\s+(\S+)', line)
            if ip_m: l3_data.append({'name': ip_m.group(2), 'ip': ip_m.group(1)})

    net_connect.disconnect()

    # --- SYNC KE NETBOX ---
    print(f"\n✅ Data Terambil: {model} [SN: {serial_number}]")
    
    # PERHATIAN: Pastikan "DC Cibinong" ini benar ada di NetBox Mas.
    site = nb.dcim.sites.get(name="DC Cibinong")
    if not site:
        sys.exit("❌ Error: Site 'DC Cibinong' tidak ditemukan di NetBox! Buat dulu site-nya.")

    mfg_n = v_data['name'].split()[0]
    mfg = nb.dcim.manufacturers.get(name=mfg_n) or nb.dcim.manufacturers.create(name=mfg_n, slug=make_slug(mfg_n))
    dt = nb.dcim.device_types.get(model=model) or nb.dcim.device_types.create(model=model, slug=make_slug(model), manufacturer=mfg.id)
    dev = nb.dcim.devices.get(name=TARGET_NAME) or nb.dcim.devices.create(name=TARGET_NAME, device_type=dt.id, role=7, site=site.id, serial=serial_number)
    if serial_number: dev.serial = serial_number; dev.save()

    print(f"⏳ Sync {len(ports_data)} Physical Ports...")
    for p in ports_data:
        print(f"  {'🟢' if p['status'] else '🔴'} {p['name']} - {p['desc']}")
        nb_p = nb.dcim.interfaces.get(device_id=dev.id, name=p['name']) or nb.dcim.interfaces.create(device=dev.id, name=p['name'], type=p.get('type','other'), enabled=p['status'], description=p['desc'])
        nb_p.enabled = p['status']; nb_p.description = p['desc']; nb_p.save()

    print(f"⏳ Sync VLAN/L3 Interfaces...")
    for v in l3_data:
        print(f"  🔷 {v['name']} - {v['ip']}")
        nb_v = nb.dcim.interfaces.get(device_id=dev.id, name=v['name']) or nb.dcim.interfaces.create(device=dev.id, name=v['name'], type='virtual')
        try:
            addr_final = IP_FULL if v['ip'] == IP_ADDR else f"{v['ip']}/24"
            nb_ip = nb.ipam.ip_addresses.get(address=v['ip']) or nb.ipam.ip_addresses.create(address=addr_final, status='active', assigned_object_type='dcim.interface', assigned_object_id=nb_v.id)
            if v['ip'] == IP_ADDR: dev.primary_ip4 = nb_ip.id; dev.save()
        except: pass

    print(f"\n✨ Sinkronisasi Selesai: {len(ports_data)} port fisik dan {len(l3_data)} interface L3 berhasil disinkronisasi.")

except KeyboardInterrupt:
    console.print("\n[yellow]Proses dibatalkan oleh pengguna.[/yellow]")
    sys.exit(0)
except Exception as e:
    console.print(f"[bold red]❌ Terjadi kesalahan: {e}[/bold red]")
    sys.exit(1)
