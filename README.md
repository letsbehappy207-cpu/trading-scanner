# LQ45 Telegram Screener

Screener sederhana untuk 52 saham LQ45 (data Yahoo Finance, gratis, delay
~15 menit) yang broadcast sinyal ke Telegram 2x sehari lewat GitHub Actions
(gratis, tidak butuh server sendiri).

**Bukan bandarmology asli** — tidak ada data broker summary di sini karena
itu berbayar dan tidak tersedia via API gratis. Sinyal di sini murni dari
price-action + volume publik: volume spike, breakout dari base sideways,
RSI. Anggap ini alat bantu screening awal, bukan rekomendasi pasti.

## Setup (sekali saja)

1. **Push folder ini ke repo GitHub baru** (bisa private, gratis):
   ```
   cd trading-screener
   git init
   git add .
   git commit -m "Initial screener"
   git branch -M main
   git remote add origin https://github.com/<username>/<repo>.git
   git push -u origin main
   ```

2. **Ambil Chat ID Telegram Anda:**
   - Kirim pesan apa saja ke bot Anda (`@morningkimi_bot`) di Telegram dulu.
   - Buka di browser: `https://api.telegram.org/bot<TOKEN>/getUpdates`
     (ganti `<TOKEN>` dengan token bot Anda).
   - Cari angka di `"chat":{"id": ...}` — itu Chat ID Anda.

3. **Simpan token & chat ID sebagai GitHub Secrets** (bukan di kode):
   - Buka repo di GitHub → Settings → Secrets and variables → Actions → New repository secret.
   - Tambahkan `TELEGRAM_BOT_TOKEN` = token bot Anda.
   - Tambahkan `TELEGRAM_CHAT_ID` = chat ID dari langkah 2.

4. **Aktifkan Actions** (kalau repo baru, biasanya sudah aktif otomatis).
   Cek tab **Actions** di repo → workflow "LQ45 Telegram Screener" akan
   otomatis jalan sesuai jadwal:
   - 08:30 WIB (hari bursa) → broadcast sinyal screening pagi
   - 16:15 WIB (hari bursa) → rekap penutupan sore

5. **Tes manual dulu** sebelum nunggu jadwal: tab Actions → pilih workflow
   ini → tombol "Run workflow" → jalankan manual, cek apakah pesan masuk
   ke Telegram Anda.

## File

- `main.py` — entry point, fetch data + kirim ke Telegram
- `indicators.py` — perhitungan RSI, volume spike, breakout, skor sinyal
- `tickers_lq45.py` — daftar saham (approx. LQ45, cek ulang tiap Feb/Agu
  saat IDX rilis komposisi baru — daftar saat ini bisa sedikit meleset)
- `.github/workflows/screener.yml` — jadwal otomatis GitHub Actions

## Update watchlist

Edit `tickers_lq45.py` kapan saja, commit & push — jadwal berikutnya
otomatis pakai daftar baru.
