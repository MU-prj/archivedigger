# Internet Archive: analisi delle API per ricerca e download audio

Analisi di riferimento delle capacità di filtraggio offerte da Internet Archive
(IA) e dalla libreria Python ufficiale `internetarchive`, su cui si fonda
archivedigger. Serve come base per la mappatura filtro → flag CLI → campo YAML.

## 1. Modello dei dati di IA

IA è organizzato in **item** (unità di conservazione, identificata da un
`identifier` univoco). Ogni item contiene **file** (le tracce audio, i derivati,
i metadati) ed è descritto da **metadati** (campi indicizzati). Un item può
appartenere a più **collezioni**.

L'audio vive in due `mediatype`:

- **`audio`** — musica, field recording, radio, podcast, audiolibri, spoken word.
- **`etree`** — Live Music Archive: registrazioni di concerti dal vivo di band
  che ne consentono la condivisione, spesso in lossless (FLAC/SHN).

## 2. Ricerca item-level (Advanced Search / Scraping API)

La ricerca usa sintassi **Lucene** (`campo:valore`, booleani `AND/OR/NOT`,
range `[a TO b]`, wildcard `*`). `internetarchive.search_items()` la incapsula:

```python
search_items(query, fields=None, sorts=None, params=None,
             archive_session=None, config=None, config_file=None,
             http_adapter_kwargs=None, request_kwargs=None, max_retries=None)
```

- `query` — stringa Lucene, es. `mediatype:(audio OR etree) AND collection:foo`.
- `fields` — lista di campi metadati da restituire per ciascun hit.
- `sorts` — lista di ordinamenti, es. `["downloads desc"]`.
- Per grandi volumi la libreria usa la **Scraping API** (paginazione a cursore),
  che permette di iterare su milioni di risultati.

### Campi indicizzati principali (queryabili e ordinabili)

| Campo | Significato | Uso in archivedigger |
|---|---|---|
| `identifier` | ID univoco dell'item | chiave nel manifest |
| `mediatype` | `audio`, `etree`, ... | `--mediatype` |
| `collection` | collezione/e di appartenenza | `--collection` (ripetibile) |
| `creator` | autore/artista | `--creator` |
| `title` | titolo | `--title` |
| `subject` | tag tematici | `--subject` (ripetibile) |
| `description` | descrizione | `--description` |
| `language` | lingua | `--language` |
| `date` | data del contenuto | `--date-from` / `--date-to` |
| `year` | anno del contenuto | `--year-from` / `--year-to` |
| `addeddate` / `publicdate` | data di upload su IA | `--added-after` / `--added-before` |
| `licenseurl` | URL della licenza | `--license`, `--license-url` |
| `downloads` | numero di download | `--min-downloads`, sort default |
| `item_size` | dimensione totale item (byte) | `--min-item-size` / `--max-item-size` |
| `avg_rating` | valutazione media | `--min-rating` |
| `format` | formati file presenti nell'item | filtro grezzo lato ricerca |

### Preset licenza (`--license`)

Mappati su pattern di `licenseurl`:

- `publicdomain` → `licenseurl:*publicdomain*` o `*creativecommons.org/publicdomain*`.
- `cc` → qualsiasi `*creativecommons.org/licenses/*`.
- `cc-commercial` → CC che **non** contengono `nc` (uso commerciale permesso).
- `any` → nessun filtro sulla licenza (default).

## 3. Selezione dei file (file-level)

Ogni item espone `item.files`: lista di dict con `name`, `format`, `size`,
`md5`, `length` (durata in secondi, quando presente), `source`
(`original` vs `derivative`), ecc.

`internetarchive` offre due vie complementari:

```python
Item.get_files(files=None, formats=None, glob_pattern=None,
               exclude_pattern=None, on_the_fly=False)

Item.download(files=None, formats=None, glob_pattern=None, exclude_pattern=None,
              dry_run=False, verbose=False, ignore_existing=False,
              checksum=False, checksum_archive=False, destdir=None,
              no_directory=False, retries=None, item_index=None,
              ignore_errors=False, on_the_fly=False, return_responses=False,
              no_change_timestamp=False, ignore_history_dir=False,
              source=None, exclude_source=None, stdout=False, params=None,
              timeout=None, count_views=False, headers=None, range_jobs=None)
```

Parametri rilevanti per i nostri filtri e modalità:

- `formats` — filtra per formato IA (es. `"Flac"`, `"VBR MP3"`, `"24bit Flac"`).
- `glob_pattern` / `exclude_pattern` — pattern sui nomi file (es. `"*.flac"`).
- `source` / `exclude_source` — `original` vs `derivative`.
- `dry_run` — non scarica, restituisce le URL: base per la stima.
- `checksum` — salta i file già presenti se l'MD5 coincide (**resume checksum**).
- `ignore_existing` — salta i file già presenti per sola esistenza (**fast-skip**).
- `destdir` / `no_directory` — cartella di destinazione / niente sottocartella item.
- `retries` — retry per singolo file.
- `ignore_errors` — un file/item rotto non ferma il batch.
- `return_responses` — utile in test per ispezionare senza scrivere su disco.

**Nota architetturale**: `formats`/`glob` di `internetarchive` coprono il filtro
*esatto*. La **catena di preferenza** (`prefer`) e i filtri su **durata/size/dedup**
NON esistono nella libreria: archivedigger li implementa lato client come
strategy, selezionando i `File` da passare poi a `download(files=...)`.

### Nomi di formato IA più comuni per l'audio

Lossless: `Flac`, `24bit Flac`, `AIFF`, `WAVE`, `Shorten`.
Lossy: `VBR MP3`, `128Kbps MP3`, `64Kbps MP3`, `Ogg Vorbis`, `Ogg Video`.
Derivati/altro: `Spectrogram`, `PNG`, `Metadata`, `Item Tile`.

## 4. Implicazioni per archivedigger

1. **Filtro ricerca** → costruzione della query Lucene da campi YAML/flag;
   nessun campo impostato ⇒ nessuna clausola ⇒ nessuna restrizione.
2. **Selezione formato** → strategy: `ExactFormatStrategy` (usa `formats`) o
   `PreferenceChainStrategy` (sceglie il miglior gruppo disponibile per item,
   con gruppi a pari merito).
3. **Filtri file** → catena di `FileFilter` strategy (durata, size, dedup)
   applicata alla lista `item.files` prima del download.
4. **Download** → mappatura modalità (resume, workers, retries, layout, budget)
   sui parametri di `Item.download`, con il manifest JSONL come registro esterno.

## Fonti

- `internetarchive` docs: <https://internetarchive.readthedocs.io/>
- Signature verificate su `internetarchive/item.py` (branch master, lug 2026).
- Advanced Search: <https://archive.org/advancedsearch.php>
- Scraping API: <https://archive.org/services/search/v1/scrape>
- Metadata schema: <https://archive.org/developers/metadata-schema/>
