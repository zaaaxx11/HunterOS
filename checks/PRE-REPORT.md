# PRE-REPORT CHECKLIST — HUNT-OS

Jalankan sebelum setiap report keluar. Satu item gagal = report tidak keluar.

## Evidence
- [ ] Setiap finding punya poc_path yang EXISTS di disk
- [ ] Setiap finding proven-live punya evidence_ref (tx hash / receipt / exchange log)
- [ ] Setiap finding theoretical diberi label eksplisit (bukan diam-diam dikira proven)
- [ ] Tidak ada klaim "submitted" yang belum diverifikasi (explorer / response body)

## Adversary
- [ ] Setiap concrete finding sudah blind-adversary reviewed
- [ ] Setiap overturn tercatat + alasannya (terminal, tidak dihidupkan lagi tanpa bukti baru)

## Waves
- [ ] Re-audit wave sebelumnya tercatat sebelum wave berikut dibuka
- [ ] Verdict tiap wave: continue / exhausted / pivot — ada alasannya

## Report
- [ ] Impact chain lengkap per finding (trigger → effect → boundary)
- [ ] Falsifier tercatat per finding
- [ ] Tidak ada em-dash, tidak ada AI-slop
- [ ] Human tone, English, PoC embedded
- [ ] Real tool output only — tidak ada fabricated data

## Retro
- [ ] Lessons di-record setelah report keluar
- [ ] Pattern candidate (muncul ≥2 target) diusulkan untuk promotion
