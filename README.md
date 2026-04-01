# 📦 Tuibox: Alat Sinkronisasi Aset IT ke NetBox

Tuibox adalah solusi terpadu berbasis Python yang dirancang untuk mengotomatisasi dan menyederhanakan proses sinkronisasi data aset IT Anda dari berbagai lingkungan (seperti platform virtualisasi dan perangkat jaringan) ke dalam NetBox. Tujuannya adalah untuk meningkatkan efisiensi operasional, mengurangi kesalahan manual, dan memastikan konsistensi serta akurasi data inventaris infrastruktur Anda.

## ✨ Mengapa Tuibox?

*   **Penyedia Data Terpusat**: Menggabungkan fungsionalitas dari beberapa skrip sinkronisasi ke dalam satu *framework* yang mudah digunakan.
*   **Efisiensi Operasional**: Mengotomatisasi pembaruan data yang memakan waktu, memungkinkan tim fokus pada tugas-tugas strategis.
*   **Akurasi Data**: Memastikan NetBox Anda selalu mencerminkan kondisi infrastruktur IT yang sebenarnya.
*   **Manajemen Profesional**: Mendorong praktik terbaik dalam inventarisasi dan manajemen aset.

## 🚀 Fitur Utama

Tuibox hadir dengan serangkaian fitur untuk menjaga data NetBox Anda tetap mutakhir:

### 🌐 Integrasi Data Multi-platform

*   **Virtualisasi**: Sinkronisasi *Virtual Machines* (VM) secara otomatis dari:
    *   Hyper-V (`sync_hyperv_netbox.py`)
    *   KVM (`sync_kvm_netbox.py`)
    *   Proxmox (`sync_proxmox_netbox.py`)
    *   VMware (`sync_vmware_netbox.py`)
*   **Jaringan**: Sinkronisasi konfigurasi perangkat jaringan (switch, router) dari berbagai vendor dengan `sync_switch.py`.
*   **MikroTik Spesifik**: Sinkronisasi IPAM dan DCIM yang mendalam untuk perangkat MikroTik melalui skrip `tuibox` utama.

### 📊 Manajemen IPAM Cerdas

*   **Deteksi Prefix Otomatis**: Secara cerdas mengidentifikasi, membuat, dan memperbarui objek Prefix di NetBox untuk setiap alamat IP yang disinkronkan, memastikan konsistensi data subnet.
*   **Deteksi IP Aktif yang Akurat**:
    *   Meningkatkan algoritma deteksi perangkat aktif melalui pemindaian **ARP**, **DHCP Leases**, dan **Neighbor** dari perangkat jaringan.
    *   Memastikan alamat IP perangkat router sendiri selalu diakui sebagai aktif.
    *   Timeout `ping_sweep` dioptimalkan (dari 5ms menjadi 50ms) untuk mengurangi *false positive* pada IP yang 'offline', terutama pada perangkat yang responsnya lambat.
*   **Sinkronisasi Mask IP**: Memastikan *subnet mask* yang benar dari sumber (MikroTik, KVM, Proxmox) disinkronkan ke NetBox, bukan hanya IP tanpa *mask*.

### ⚙️ Konfigurasi Fleksibel & Keamanan

*   **Opsi Konfigurasi Ganda**: Mendukung konfigurasi melalui file `.env` (direkomendasikan untuk keamanan) atau input interaktif yang mudah saat skrip dijalankan.
*   **Penanganan Error Robust**: Memberikan notifikasi yang jelas dan keluar dengan aman saat terjadi kesalahan atau interupsi.
*   **Laporan Ringkas**: Menyajikan ringkasan tindakan yang dilakukan (misalnya, jumlah item yang dibuat, diperbarui, atau dipetakan) setelah setiap proses sinkronisasi selesai.

## 📝 Cara Penggunaan

Ikuti langkah-langkah sederhana ini untuk memulai Tuibox:

1.  **Prasyarat**:
    *   Pastikan Anda memiliki **Python 3** terinstal.
    *   Instal pustaka Python yang diperlukan menggunakan `pip`:
        ```bash
        pip install pynetbox netmiko rich requests
        # Perhatikan: modul `ipaddress` adalah bawaan Python 3.x
        ```

2.  **Konfigurasi**:
    *   Buat file `.env` di direktori `tuibox/` (contoh: `cp config.ini.example .env`).
    *   Edit file `.env` dengan detail koneksi ke NetBox, serta kredensial untuk server virtualisasi/jaringan Anda.
    *   *Alternatif*: Jika file `.env` tidak ditemukan, skrip akan memandu Anda melalui input interaktif.

3.  **Eksekusi**:
    *   Jalankan skrip Python yang relevan dari direktori `tuibox/` menggunakan Python 3.
    *   Contoh: Untuk sinkronisasi KVM, jalankan `python3 sync_kvm_netbox.py`
    *   Contoh: Untuk sinkronisasi MikroTik, jalankan `python3 tuibox`

## 📜 Lisensi

Proyek ini dirilis di bawah lisensi **MIT**. Lihat file `LICENSE` untuk detail selengkapnya.

---

*Dikembangkan dengan ❤️ untuk efisiensi dan profesionalisme dalam manajemen infrastruktur IT.*
