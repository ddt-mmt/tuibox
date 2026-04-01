# Tuibox

Tuibox adalah sebuah alat terpadu yang dirancang untuk menyederhanakan proses sinkronisasi data aset IT dari berbagai lingkungan (virtualisasi dan jaringan) ke dalam NetBox. Alat ini menggabungkan fungsionalitas dari skrip-skrip sinkronisasi terpisah untuk meningkatkan efisiensi, meminimalkan redundansi, dan memastikan konsistensi data di seluruh infrastruktur Anda.

## Tujuan

Tujuan utama dari Tuibox adalah:
*   Menyediakan satu titik akses untuk mengelola sinkronisasi data infrastruktur ke NetBox.
*   Meningkatkan efisiensi operasional dengan mengotomatisasi tugas-tugas manual.
*   Memastikan akurasi dan kelengkapan data aset IT di NetBox.
*   Memelihara standar profesionalisme dalam manajemen inventaris infrastruktur.

## Fitur Utama

*   **Konsolidasi Skrip Sinkronisasi**: Mengintegrasikan fungsionalitas dari skrip-skrip untuk:
    *   Sinkronisasi Virtual Machines (VM) dari Hyper-V, KVM, Proxmox, dan VMware ke NetBox.
    *   Sinkronisasi konfigurasi perangkat jaringan (switch, router) ke NetBox.
*   **Manajemen IPAM yang Ditingkatkan**:
    *   **Deteksi Prefix Otomatis**: Secara cerdas mendeteksi dan membuat/memperbarui objek Prefix di NetBox untuk setiap IP yang disinkronkan, memastikan konsistensi data subnet.
    *   **Deteksi IP Aktif yang Akurat**: Meningkatkan algoritma deteksi IP yang aktif (melalui ARP, DHCP, Neighbor, dan ping sweep), serta memastikan IP perangkat router sendiri selalu dianggap aktif. Timeout `ping_sweep` telah dioptimalkan untuk mengurangi *false positive* pada IP yang 'offline'.
    *   **Sinkronisasi Mask IP**: Memastikan subnet mask yang benar dari sumber (MikroTik, KVM, Proxmox) disinkronkan ke NetBox.
*   **Manajemen Konfigurasi Fleksibel**: Mendukung konfigurasi melalui file `.env` atau input interaktif saat skrip dijalankan, memastikan keamanan data sensitif.
*   **Penanganan Error dan Interupsi**: Memberikan notifikasi yang jelas dan keluar dengan bersih saat terjadi error atau pembatalan oleh pengguna.
*   **Notifikasi yang Jelas**: Memberikan ringkasan tentang tindakan yang dilakukan (misalnya, jumlah item yang dibuat, diperbarui, atau di-mapping) setelah proses sinkronisasi selesai.

## Cara Penggunaan

1.  **Prasyarat**: Pastikan Anda memiliki Python 3 terinstal. Instal pustaka Python yang diperlukan (misalnya, `pynetbox`, `netmiko`, `rich`, `requests`, `ipaddress`) menggunakan `pip`.
2.  **Konfigurasi**: Siapkan file `.env` di direktori `tuibox/` dengan informasi koneksi ke NetBox dan server virtualisasi/jaringan Anda, atau biarkan skrip menuntun Anda melalui input interaktif saat pertama kali dijalankan.
3.  **Eksekusi**: Jalankan skrip Python yang relevan dari direktori `tuibox/` (misalnya, `python3 sync_hyperv_netbox.py`).

## Lisensi

Proyek ini dirilis di bawah lisensi **MIT**. Lihat file `LICENSE` untuk detail selengkapnya.

---

*Dikembangkan untuk efisiensi dan profesionalisme dalam manajemen infrastruktur IT.*