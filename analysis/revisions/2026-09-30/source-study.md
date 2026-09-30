# Studi sumber — revisi 02

Sumber pengendali: **LAYOUT PLAN ALT.2**, handle 165A2, pada `SEND.Pengolahan Hasil Laut - Jetis (1).dwg`.

## Bukti dari gambar

- Hash sumber: `793d4ec07d86248e5912676eea1f0c5720186aceacdef0ef97ef004aa138faf5`. Sumber asli tidak diedit.
- Ekstraksi membaca 73.672 entitas model space dan 710 definisi blok. Ada 3.111 peringatan untuk jenis data yang tidak didukung ekstraktor. Ini bukan konversi semantik seluruh DWG.
- Perbandingan dengan sumber sebelumnya: 382 handle ditambah, 316 dihapus, dan satu rekaman berubah jenis ekstraksi. Handle yang diganti bukan bukti bahwa seluruh bangunan berubah ukuran.
- Satuan model adalah meter. Label 30×78 dan 30×84 sesuai poligon, ditambah dimensi 30 dan 60 m. Arah utara mengikuti panah U ke +X; tanpa koordinat georeferensi.
- Tapak mempertahankan 12 titik, sekitar 160,129×149,069 m, luas 19.054,227 m². Bangunan tahap 1: 78×30 m dan 84×30 m; dua sayap 36×30 m. Tahap 2 berbentuk trapesium sedalam 84 m dengan lebar berubah 36→30 m.
- Potongan A-A dan B-B menempatkan lantai utama ±0. Nilai +1 m adalah kepala pedestal. Potongan C-C menunjukkan lantai atas +4,50 m sepanjang baris 120 m. Detail WF300 sedalam 0,30 m adalah rangka, bukan ukuran tebal pelat.
- Atap tahap 1 menerus pada baris 114 m dan 120 m. Garis penutup sumber memiliki kemiringan 15°. Nilai +9 m adalah acuan tumpuan; penutup atap dan puncak mengikuti profil sumber yang diselaraskan ke puncak nominal +13,50 m. Atap tahap 2 mempertahankan poligon meruncing dari denah atap.
- Detail baru: jembatan timbang 15×4 m; ruang pencatatan sumbu 3×3 m, dinding 0,15 m, pintu P90 ke dalam, jendela selatan 1,50 m; modul 12×12 m dengan tangga lebar 0,90 m, injakan 0,30 m, dua landing dan void bertingkat.
- Tampak industri menggambar pintu dua daun dengan handel. Ambang berada +1,20 m. Ruang pencatatan memakai pintu berengsel sesuai blok sumber.

## Keputusan Bam dan asumsi model

Bam memilih lantai utama ±0 dan ambang pintu +1,20 m sekaligus. Platform loading, tangga akses dan akses barang menghubungkan kedua elevasi tersebut; ukurannya adalah asumsi visual.

Lantai atas dimodelkan pada seluruh 120×30 m dengan void sumber. Isi pelat dan tebal 0,15 m adalah inferensi studi visual dari garis lantai/rangka potongan. Tangga memakai 30 kenaikan masing-masing 0,15 m untuk mencapai +4,50 m; susunan denah sumber tetap dipertahankan.

Pintu industri memakai gerak geser dua daun sebagai asumsi mekanisme. Dimensi dan posisi mengikuti tampak. Detail flange/web WF, sambungan, pondasi, isi proses, peralatan, material dan lanskap yang tidak lengkap pada gambar tetap asumsi. Hasil ini bukan persetujuan rekayasa struktur.

## Penyerahan

Luna dan Astra mempertahankan repo serta Pages masing-masing. Output native revisi dibuat langsung dengan pustaka C API SketchUp lokal sesuai instruksi Bam, tanpa menggunakan MCP SketchUp. Verifikasi native dilakukan dengan memuat ulang file melalui pustaka yang sama; ini dibedakan dari buka ulang melalui antarmuka aplikasi.

## Source-window enumeration
Raw kusen polylines of 0.70 � 1.14 m enumerate 42 frames: 36 upper and 2 lower on the south elevation, plus 4 lower on the east elevation (216CD/216D3/216D9/216DF). East sill is 1.26 m above floor-line 21670. These are source dimensions; room-window heights remain assumptions.

## Purlin spacing evidence
The explicit AA aligned dimensions1791C–17942 measure1.20m along the15° roof slope (horizontal projection1.159111m);17943 measures the terminal0.80m. T2 layerHAT roof-plan lines are spaced1.20m horizontally and have no CNP axis label. The locked slope spacing takes precedence; this3.53% projection mismatch is recorded as a drawing ambiguity, not converted into a new structural specification.
