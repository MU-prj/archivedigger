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

## Uso come CLI

```sh
# Elenca i profili preset
archivedigger profiles

# Esegui un job dichiarativo (YAML), con override da flag
archivedigger run docs/example-job.yaml --max-items 50 --dry-run

# Solo ricerca: stampa gli identifier che matchano
archivedigger search --collection field-recordings --license cc --min-downloads 100

# Stima (dry-run) di quanto scaricheresti
archivedigger estimate --profile corpus --collection etree

# Download reale con profilo + preferenza di formato + budget
archivedigger run --profile corpus \
    --creator "John Coltrane" \
    --prefer "Flac=AIFF=WAVE>VBR MP3" \
    --min-duration 30 --dedup \
    --destdir ./downloads --size-budget 20

# Esporta il manifest in CSV
archivedigger export-manifest ./downloads/manifest.jsonl -o report.csv
```

La precedenza è: **flag CLI > job YAML > profilo > default**. Nessun filtro
impostato significa nessuna restrizione.

## Uso come libreria (external)

```python
from archivedigger import Config, dig

config = Config.build(
    profile="corpus",
    job={
        "search": {"collection": ["field-recordings"], "license": "cc"},
        "filters": {"min_duration": 30, "dedup": True},
        "download": {"destdir": "./corpus", "size_budget_gb": 10},
    },
)
report = dig(config)
print(report.downloaded, report.bytes_downloaded)
```

Le strategy (formati, filtri file, resume, layout) sono estendibili: un repo
consumatore può registrare le proprie senza modificare il core.

## Struttura

```
docs/    documentazione e idee emerse durante le sessioni
src/     codice del package (src-layout)
tests/   suite pytest (unit offline + integration opzionali)
```

## Licenza

[CC BY 4.0](LICENSE) — Domenico Nasso.
