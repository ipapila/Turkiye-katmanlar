/**
 * server.js — Web sunucusu + günlük cron
 * ----------------------------------------
 * Statik dosyaları (HTML, data.json) sunar ve
 * her gün belirlenen saatte otomatik güncelleme yapar.
 *
 * Başlatmak için:
 *   node server.js
 *
 * Arka planda çalıştırmak için (PM2):
 *   pm2 start server.js --name antalya-ekoloji
 *   pm2 save && pm2 startup
 */

require('dotenv').config();
const express = require('express');
const cron    = require('node-cron');
const path    = require('path');
const fs      = require('fs');
const { runUpdate } = require('./scripts/update');

const app  = express();
const PORT = process.env.PORT || 3000;
const HOUR = parseInt(process.env.CRON_HOUR || '6', 10);   // varsayılan 06:00
const TOKEN = process.env.UPDATE_TOKEN || null;

// ── Statik dosyalar (public/) ────────────────────────────────────────────────
app.use(express.static(path.join(__dirname, 'public')));

// ── /status — sistem durumu ──────────────────────────────────────────────────
app.get('/status', (req, res) => {
  const dataFile = path.join(__dirname, process.env.DATA_FILE || 'public/data.json');
  let info = { status: 'ok', cron_hour: HOUR, uptime_sec: Math.floor(process.uptime()) };
  try {
    if (fs.existsSync(dataFile)) {
      const d = JSON.parse(fs.readFileSync(dataFile, 'utf8'));
      info.last_update = d.updated_at_tr;
      info.record_count = d.count;
    } else {
      info.data_file = 'henüz oluşturulmadı';
    }
  } catch(e) { info.data_error = e.message; }
  res.json(info);
});

// ── /update?token=XXX — manuel güncelleme tetikleyici ───────────────────────
app.get('/update', async (req, res) => {
  if (TOKEN && req.query.token !== TOKEN) {
    return res.status(403).json({ error: 'Geçersiz token' });
  }
  console.log('[server] Manuel güncelleme tetiklendi — IP:', req.ip);
  res.json({ message: 'Güncelleme başlatıldı, arka planda devam ediyor...' });
  try { await runUpdate(); } catch(e) { console.error('[server] Manuel güncelleme hatası:', e.message); }
});

// ── Cron: her gün HOUR:00'da çalış ──────────────────────────────────────────
const cronExpr = `0 ${HOUR} * * *`;
cron.schedule(cronExpr, async () => {
  console.log(`[cron] Günlük güncelleme başlıyor — ${new Date().toLocaleString('tr-TR')}`);
  try {
    const result = await runUpdate();
    console.log(`[cron] Tamamlandı — yeni: ${result.added}, toplam: ${result.total}`);
  } catch (e) {
    console.error('[cron] Hata:', e.message);
  }
}, { timezone: 'Europe/Istanbul' });

console.log(`[server] Cron ayarlandı: her gün ${HOUR}:00 (İstanbul saati)`);

// ── Sunucuyu başlat ──────────────────────────────────────────────────────────
app.listen(PORT, () => {
  console.log(`[server] Çalışıyor → http://localhost:${PORT}`);
  console.log(`[server] Durum     → http://localhost:${PORT}/status`);
  if (TOKEN) console.log(`[server] Manuel güncelleme → http://localhost:${PORT}/update?token=${TOKEN}`);

  // İlk başlangıçta data.json yoksa hemen bir güncelleme yap
  const dataFile = path.join(__dirname, process.env.DATA_FILE || 'public/data.json');
  if (!fs.existsSync(dataFile)) {
    console.log('[server] data.json bulunamadı, ilk güncelleme başlatılıyor...');
    runUpdate().catch(e => console.error('[server] İlk güncelleme hatası:', e.message));
  }
});
