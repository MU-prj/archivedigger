# Piano 0001 — Bootstrap di archivedigger

Piano di sviluppo del downloader audio da Internet Archive, da realizzare in
**TDD** (red-green-refactor, skill `/tdd`). Le decisioni sono state fissate in
una sessione grill-me con Domenico Nasso (2026-07-02/03).

## Obiettivo

Package Python `archivedigger` + CLI omonima, installabile come dipendenza
esterna in altri repository, che cerca e scarica in massa file audio da IA con
filtri completi, job YAML dichiarativi e download robusto/riavviabile.

## Decisioni fissate (grill-me)

| # | Tema | Decisione |
|---|---|---|
| D1 | Caso d'uso | Corpus + mirror + dataset, modulabili tra loro (3 profili preset) |
| D2 | Naming | repo/package/CLI = `archivedigger` |
| D3 | Repo | Pubblico in **MU-prj**, licenza **CC BY 4.0** |
| D4 | Mediatype | `audio` + `etree` di default, modulabile via flag/YAML |
| D5 | Filtri ricerca | Tutti i campi indicizzati come flag; assenza filtro = nessuna restrizione |
| D6 | Config | **YAML dichiarativo** come sorgente primaria + flag CLI che sovrascrivono |
| D7 | Sort & limiti | `--max-items` default 100 (0=illimitato), `--sort` default `downloads desc`, `--size-budget` GB |
| D8 | Formati | `--formats` (esatto) **e** `--prefer` (catena); FLAC=AIFF=WAVE a pari merito in cima; selezione anche di un singolo tipo |
| D9 | Filtri file | durata min/max, size file min/max, dedup MD5 (per ora) |
| D10 | **Strategy** | filtri e selezioni implementati come **pattern Strategy** intercambiabili, componibili da YAML, estendibili dai consumatori |
| D11 | Resume | modulabile tra checksum MD5 (default) e fast-skip (esistenza), più `--force` |
| D12 | Concorrenza | 4 worker default, retry 3 con backoff, ignore-errors nel batch |
| D13 | Manifest | **JSONL** (append-safe) + export CSV; YAML solo per la config |
| D14 | Layout disco | `destdir/<collection>/<identifier>/<file>`, con `--flat`/`--layout item` |
| D15 | CLI | **argparse** (stdlib, zero dipendenze extra) |
| D16 | Python | **>=3.11** |
| D17 | Testing | fake offline (fixture JSON) + integration opzionali (`-m integration`) |
| D18 | Makefile | target venv/install/test/test-integration/lint/format/clean |

## Precedenza di configurazione

`flag CLI` > `job YAML` > `profilo` > `default del package`.

Ogni campo omesso ricade sul livello sotto; nessun filtro ⇒ nessuna clausola
Lucene ⇒ nessuna restrizione.

## Architettura a strategy (D10)

Interfacce comuni, implementazioni intercambiabili, selezionate da config e
sovrascrivibili/estendibili dai repo consumatori.

- **`SearchFilter`** — traducono i campi di config in clausole della query
  Lucene. Una per famiglia (collezione, date, licenza, popolarità...). Il
  `QueryBuilder` le compone; l'assenza di una filter = nessuna clausola.
- **`FormatStrategy`** — dato `item.files`, seleziona quali file scaricare:
  - `ExactFormatStrategy` (usa `formats`/`glob`),
  - `PreferenceChainStrategy` (gruppi ordinati, pari merito interno; per ogni
    item sceglie il primo gruppo con almeno un file disponibile).
- **`FileFilter`** — predicati componibili sui singoli `File`
  (`DurationFilter`, `FileSizeFilter`, `Md5DedupFilter`). Applicati in catena.
- **`ResumePolicy`** — `ChecksumResume`, `FastSkipResume`, `ForceRedownload`.
- **`DiskLayout`** — `CollectionLayout`, `ItemLayout`, `FlatLayout`.

Tutte registrabili per nome, così un YAML può dire `resume: checksum` e un repo
esterno può registrare la propria strategy senza toccare il core.

## Moduli previsti (src/archivedigger/)

```
config.py       Config dataclass + merge (default < profilo < YAML < flag)
profiles/       corpus.yaml, mirror.yaml, dataset.yaml (package-data)
query.py        QueryBuilder + SearchFilter (campi -> Lucene)
client.py       ArchiveClient: wrapper su internetarchive (search/get_files/
                download), unica superficie da mockare nei test
formats.py      FormatStrategy (Exact, PreferenceChain)
filters.py      FileFilter (Duration, FileSize, Md5Dedup) + catena
resume.py       ResumePolicy (Checksum, FastSkip, Force)
layout.py       DiskLayout (Collection, Item, Flat)
manifest.py     Manifest JSONL (append/read) + export CSV
downloader.py   orchestratore bulk: worker pool, retry/backoff, budget, dry-run
cli.py          argparse: sottocomandi + tutte le flag; entrypoint main()
api.py          facciata pubblica per l'uso come libreria (dig(config))
```

## CLI prevista

Sottocomandi:

- `archivedigger run [JOB.yaml] [flag...]` — esegue un job (YAML + override).
- `archivedigger search [flag...]` — solo ricerca, stampa gli item (no download).
- `archivedigger estimate [...]` — dry-run: stima item/file/GB.
- `archivedigger export-manifest MANIFEST.jsonl -o out.csv` — export CSV.
- `archivedigger profiles` — elenca i profili disponibili.

Flag (sovrascrivono lo YAML) raggruppate per famiglia — ricerca: `--query`,
`--mediatype`, `--collection`, `--creator`, `--title`, `--subject`,
`--description`, `--language`, `--date-from/-to`, `--year-from/-to`,
`--added-after/-before`, `--license`, `--license-url`, `--min-downloads`,
`--min-item-size/--max-item-size`, `--min-rating`, `--sort`, `--max-items`;
file: `--formats`, `--prefer`, `--glob`, `--exclude-glob`, `--source`,
`--min-duration/--max-duration`, `--min-file-size/--max-file-size`, `--dedup`;
download: `--destdir`, `--layout`, `--flat`, `--workers`, `--retries`,
`--resume`, `--force`, `--ignore-errors/--no-ignore-errors`, `--size-budget`,
`--dry-run`, `--manifest`, `--profile`.

## Roadmap TDD (ordine di implementazione)

Ogni fase è un ciclo red-green-refactor con commit atomici; ogni modulo nasce
dai suoi test con fixture offline.

1. **config**: dataclass, merge di precedenza, caricamento profili. *(fondamenta)*
2. **query**: QueryBuilder + SearchFilter, inclusi i preset licenza e i range date.
3. **formats**: ExactFormatStrategy e PreferenceChainStrategy su file finti.
4. **filters**: DurationFilter, FileSizeFilter, Md5DedupFilter + catena.
5. **manifest**: scrittura/lettura JSONL, export CSV, round-trip.
6. **resume + layout**: policy e layout come strategy pure.
7. **client**: wrapper su internetarchive con la libreria mockata (contratto).
8. **downloader**: orchestrazione bulk (dry-run, budget, retry, worker) su client fake.
9. **cli**: parsing argparse → Config, dispatch sottocomandi, end-to-end su fake.
10. **api**: facciata `dig(config)` per i consumatori esterni; smoke test import.
11. **integration** (opzionali): una ricerca reale piccola e un download di 1 file.

## Definition of Done del bootstrap

- Fasi 1–10 verdi, `make test` pulito, `make lint` pulito.
- README con esempi d'uso come libreria e come CLI.
- Almeno un job YAML di esempio funzionante in dry-run.
- Piano spostato in `docs/plans/done/` prima del merge.
