# Piano 0002 — Prossimi passi

Roadmap dopo il bootstrap (piano 0001, chiuso). Lavoro futuro + note della
sessione di test del 2026-07-03.

## Backlog funzionale

### A. Selezione file: glob / source come strategy dedicate
`FilesConfig` ha gia' i campi `glob`, `exclude_glob`, `source` e le flag CLI
esistono, ma NON sono ancora cablati nella pipeline di selezione. Da fare:
- `GlobFilter` / `SourceFilter` come `FileFilter` (stessa interfaccia della
  catena esistente), oppure estendere `build_format_strategy` per applicarli
  dopo la selezione di formato.
- Test: item con file `original` e `derivative`, verifica che `--source
  original` tenga solo gli original; glob `*.flac` filtri per nome.

### B. Filtri file aggiuntivi (rimandati nel grill)
- ~~`--max-files-per-item N`: campiona N tracce per item~~ FATTO (2026-07-03):
  `MaxFilesPerItemFilter`, ultimo nella catena; flag `--max-files-per-item`,
  campo `filters.max_files_per_item`. Con N=1 = un file per item.
- Filtro per bitrate / sample rate se presente nei metadati file.
- Nota: `DurationFilter` tiene i file con `length` sconosciuto (non li scarta).
  Se serve durata rigida, valutare opzione "drop unknown-length".

### C. Esclusione contenuti (utile per "no musica")
IA non distingue musica da non-musica via mediatype (tutto e' `audio`). Valutare:
- `--exclude-subject` / `--exclude-collection` → clausole `NOT` in Lucene.
- preset tematici (`--kind field-recording|radio|voice`) che espandono in
  subject/collection sensati.

### D. Distribuzione
- Tag `v0.1.0` e valutare publish (GitHub release; PyPI opzionale).
- CI GitHub Actions: `make test` + `make lint` su push/PR.

### E. Osservabilita'
- Barra di avanzamento / log strutturato durante il bulk (oggi solo report finale).
- `--verbose` che stampa per-file skip/download/error in tempo reale.

## Priorita' suggerita
1. A (glob/source) — chiude un buco gia' esposto nella CLI.
2. C (esclusione contenuti) — sbloccato dal caso d'uso reale (no musica).
3. E (osservabilita') — serve appena si scaricano corpora grandi.
4. B, D — quando il core e' stabile.

## Sessione di test 2026-07-03 (1GB, no musica)

Obiettivo: validare il flusso end-to-end scaricando max 1GB di audio non
musicale (ambientale/concreto/voci/radio), preferenza lossless>lossy, solo
dedup MD5.

- Job: `docs/test-job-ambient.yaml` (profilo `corpus` + override).
- Passi: `archivedigger estimate <job>` per la stima, poi `archivedigger run
  <job>` per il download reale (budget 1GB deterministico sul piano).
- Esito e osservazioni: da annotare qui sotto dopo il run.

### Note post-run

**Test 1 — 1GB no musica (`test-job-ambient.yaml`)**
- Esito: 12 file, 0 errori, 1.09 GB, 226s.
- Bug trovato e corretto: `download_file` passava `silent=` inesistente in
  internetarchive 5.x → ogni download falliva. Colmato con test d'integrazione.
- Osservazione chiave: budget + preferenza lossless si esauriscono sul PRIMO
  item (subject "soundscape" → un audiolibro LOTR da 12 tracce). Manca varieta':
  serve cap per-item o round-robin. → motivato il feature B.

**Test 2 — ~20 clip corte 5-10s, 1/item (`test-job-shortclips.yaml`)**
- Feature B implementata (`max_files_per_item`).
- Esito: 21 item, 21 file (1/item), tutti 5.0-10.0s, 0 errori, 5.33 MB, 80.6s.
- Durate verificate sui metadati pianificati prima del download: tutte in range,
  nessun file senza `length`.
- Modalita' di selezione per-item validata end-to-end.
