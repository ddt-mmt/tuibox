# 📦 Tuibox: Alat Sinkronisasi Aset IT ke NetBox

Tuibox adalah solusi terpadu berbasis Python yang dirancang untuk mengotomatisasi dan menyederhanakan proses sinkronisasi data aset IT Anda dari berbagai lingkungan (seperti platform virtualisasi dan perangkat jaringan) ke dalam NetBox.

---

## 🐳 Docker & Portainer Deployment (Rekomendasi Produksi)

Agar layanan dapat berjalan secara stabil di latar belakang tanpa terikat pada terminal dan mudah dikelola, Tuibox mendukung penyebaran via **Docker** dan **Portainer**.

### 1. Struktur Direktori `/root/tuibox/`
```text
/root/tuibox/
├── Dockerfile          # Definisi container Python + SSHPass + Ping
├── docker-compose.yml  # Konfigurasi Docker Compose (Portainer Ready)
├── config.ini          # Konfigurasi koneksi MikroTik & NetBox API
├── README.md           # Dokumentasi proyek
└── tuibox_latest       # Skrip utama sinkronisasi
```

### 2. Cara Menjalankan via Docker Compose
Masuk ke direktori tuibox lalu jalankan:
```bash
docker compose up -d --build
```

### 3. Cara Mengelola & Troubleshooting via Portainer
1. **Melalui Portainer Stacks**:
   - Buka dashboard Portainer, pilih **Stacks** -> **tuibox-sync**.
   - Anda dapat melihat status container, melakukan restart, atau mengedit konfigurasi stack secara visual.
2. **Melihat Real-time Logs**:
   - Di Portainer, klik menu **Containers** -> pilih `tuibox-sync-service` -> klik ikon **Logs**.
   - Atau via terminal:
     ```bash
     docker logs -f tuibox-sync-service
     ```
3. **Mengatasi Restart Loop / Limit Hit**:
   - Konfigurasi Docker Compose telah dilengkapi dengan `restart: unless-stopped` dan penundaan yang aman untuk mencegah *crash loop*. Pastikan kredensial pada `config.ini` sudah benar.

---

## ✨ Fitur Utama
- **Virtualisasi**: Hyper-V, KVM (`sync_kvm_netbox.py`), Proxmox (`sync_proxmox_netbox.py`), VMware.
- **Jaringan**: Switch (`sync_switch.py`) & MikroTik (`tuibox_latest`).
- **IPAM & DCIM Cerdas**: Deteksi Prefix, IP aktif, dan sinkronisasi mask otomatis ke NetBox.

## 📝 Cara Penggunaan Manual
1. Pastikan dependensi terinstal (`requests`, `rich`, `paramiko`).
2. Konfigurasi file `config.ini`.
3. Jalankan skrip: `python3 tuibox_latest`

## 📜 Lisensi
MIT License.
