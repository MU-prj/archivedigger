# archivedigger

Downloader massivo di file audio da [Internet Archive](https://archive.org),
costruito sulla libreria ufficiale
[`internetarchive`](https://github.com/jjjake/internetarchive).

Pensato per essere usato **come dipendenza esterna in altri repository**
(package Python importabile) e **come CLI** con job YAML dichiarativi.

## Caratteristiche

- **Job YAML dichiarativi**: descrivi ricerca, filtri e modalità di download in
  un file YAML; ogni campo è sovrascrivibile da flag CLI.
- **Profili preset**: `corpus` (qualità lossless per elaborazione audio),
  `mirror` (fedeltà completa, file originali), `dataset` (volumi grandi,
  formati compressi uniformi).
- **Filtri di ricerca completi** sui campi indicizzati di IA: collezione,
  creatore, soggetto, lingua, date, licenza, popolarità, dimensione, più
  `--query` per sintassi Lucene grezza. Nessun filtro = nessuna restrizione.
- **Selezione formati** a filtro esatto (`--formats`) o a catena di preferenza
  con pari merito (`--prefer "Flac = AIFF = WAVE > VBR MP3"`).
- **Filtri file client-side** come strategy componibili: durata min/max,
  dimensione min/max, dedup MD5.
- **Bulk robusto**: 4 worker di default, retry con backoff, ripresa idempotente
  (checksum MD5 o esistenza file), budget di dimensione totale, manifest JSONL
  con export CSV.

## Stato

Bootstrap in corso — vedi [docs/plans/](docs/plans/) per il piano di sviluppo.

## Installazione

```sh
pip install git+https://github.com/MU-prj/archivedigger.git
```

Per lo sviluppo locale:

```sh
make venv install test
```

## Struttura

```
docs/    documentazione e idee emerse durante le sessioni
src/     codice del package (src-layout)
tests/   suite pytest (unit offline + integration opzionali)
```

## Licenza

[CC BY 4.0](LICENSE) — Domenico Nasso.
