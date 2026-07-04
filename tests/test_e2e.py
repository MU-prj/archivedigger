"""Test end-to-end: ogni comando e ogni funzionalita' esercitata dalla CLI
`main()` fino al filesystem, con un client finto in-memory al posto di
Internet Archive. Copre i percorsi che gli unit test tagliano fuori:
dispatch dei comandi, stampa a video, exit code, e l'interazione reale tra
selezione file, layout, resume, budget e manifest dentro un run vero.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from archivedigger.cli import main
from archivedigger.models import IAFile, IAItem


class FakeClient:
    """Client in-memory: item predefiniti, download_file scrive un file vero."""

    def __init__(self, items: list[IAItem]):
        self._items = {it.identifier: it for it in items}
        self.downloaded: list[str] = []

    def search(self, query, sort="downloads desc", max_items=100):
        return iter(list(self._items)[: max_items or None])

    def get_item(self, identifier):
        return self._items[identifier]

    def download_file(self, item, file, local_path: Path):
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(b"audio-bytes")
        self.downloaded.append(file.name)


def _item(identifier="show1", collection="jazz", files=None):
    return IAItem(
        identifier=identifier,
        metadata={"collection": collection},
        files=files or [IAFile(name="a.flac", format="Flac", size=11, md5="m1")],
    )


# --- comando estimate (mai esercitato dalla CLI negli altri test) ---


def test_e2e_estimate_prints_totals_and_exits_zero(tmp_path, capsys):
    files = [IAFile(name="a.flac", format="Flac", size=1024**3)]
    client = FakeClient([_item(files=files)])
    code = main(["estimate", "--destdir", str(tmp_path)], client=client)
    out = capsys.readouterr().out
    assert code == 0
    assert "item: 1" in out and "file: 1" in out
    assert "1.00 GB" in out
    assert client.downloaded == []  # estimate non scarica


def test_e2e_estimate_warns_on_unknown_size(tmp_path, capsys):
    files = [IAFile(name="a.flac", format="Flac", size=None)]
    code = main(["estimate", "--destdir", str(tmp_path)], client=FakeClient([_item(files=files)]))
    out = capsys.readouterr().out
    assert code == 0
    assert "senza dimensione" in out


def test_e2e_estimate_reports_errors_and_exits_one(tmp_path, capsys):
    class BrokenClient(FakeClient):
        def get_item(self, identifier):
            raise ConnectionError("503")

    code = main(["estimate", "--destdir", str(tmp_path)], client=BrokenClient([_item()]))
    out = capsys.readouterr().out
    assert code == 1
    assert "item non leggibili" in out


# --- run: ogni layout fino al filesystem ---


def test_e2e_run_collection_layout(tmp_path, capsys):
    client = FakeClient([_item(collection="etree")])
    code = main(["run", "--destdir", str(tmp_path), "--layout", "collection"], client=client)
    assert code == 0
    assert (tmp_path / "etree" / "show1" / "a.flac").exists()


def test_e2e_run_item_layout(tmp_path):
    client = FakeClient([_item()])
    main(["run", "--destdir", str(tmp_path), "--layout", "item"], client=client)
    assert (tmp_path / "show1" / "a.flac").exists()


def test_e2e_run_flat_layout_flattens_subdirs(tmp_path):
    files = [IAFile(name="disc1/a.flac", format="Flac", size=1)]
    client = FakeClient([_item(files=files)])
    main(["run", "--destdir", str(tmp_path), "--flat"], client=client)
    assert (tmp_path / "show1__disc1__a.flac").exists()


# --- resume: checksum e force attraverso due run consecutivi ---


def test_e2e_checksum_resume_skips_second_run(tmp_path, capsys):
    import hashlib

    content_md5 = hashlib.md5(b"audio-bytes").hexdigest()
    files = [IAFile(name="a.flac", format="Flac", size=11, md5=content_md5)]
    args = ["run", "--destdir", str(tmp_path), "--resume", "checksum", "--layout", "item"]

    main(args, client=FakeClient([_item(files=files)]))
    client2 = FakeClient([_item(files=files)])
    main(args, client=client2)
    assert client2.downloaded == []  # md5 combacia: saltato


def test_e2e_force_always_redownloads(tmp_path):
    files = [IAFile(name="a.flac", format="Flac", size=11, md5="m1")]
    args = ["run", "--destdir", str(tmp_path), "--layout", "item"]
    main([*args, "--resume", "checksum"], client=FakeClient([_item(files=files)]))

    client2 = FakeClient([_item(files=files)])
    main([*args, "--force"], client=client2)
    assert client2.downloaded == ["a.flac"]  # force ignora il file presente


# --- filtri e selezione file attraverso la CLI ---


def test_e2e_source_filter_excludes_derivatives(tmp_path):
    files = [
        IAFile(name="a.flac", format="Flac", size=10, source="original"),
        IAFile(name="a.mp3", format="VBR MP3", size=5, source="derivative"),
    ]
    client = FakeClient([_item(files=files)])
    main(["run", "--destdir", str(tmp_path), "--source", "original"], client=client)
    assert client.downloaded == ["a.flac"]


def test_e2e_glob_and_exclude(tmp_path):
    files = [
        IAFile(name="live/a.flac", format="Flac", size=1),
        IAFile(name="live/a.mp3", format="VBR MP3", size=1),
    ]
    client = FakeClient([_item(files=files)])
    main(
        ["run", "--destdir", str(tmp_path), "--glob", "live/*", "--exclude-glob", "*.mp3"],
        client=client,
    )
    assert client.downloaded == ["live/a.flac"]


def test_e2e_dedup_across_items(tmp_path):
    shared = IAFile(name="a.flac", format="Flac", size=1, md5="dup")
    items = [_item("i1", files=[shared]), _item("i2", files=[shared])]
    client = FakeClient(items)
    main(["run", "--destdir", str(tmp_path), "--dedup", "--layout", "item"], client=client)
    assert client.downloaded == ["a.flac"]  # il secondo item ha lo stesso md5


def test_e2e_max_files_per_item(tmp_path):
    files = [IAFile(name=f"{i}.flac", format="Flac", size=1) for i in range(5)]
    client = FakeClient([_item(files=files)])
    main(
        ["run", "--destdir", str(tmp_path), "--max-files-per-item", "2", "--layout", "item"],
        client=client,
    )
    assert len(client.downloaded) == 2


def test_e2e_size_budget_stops_run(tmp_path):
    files = [IAFile(name=f"{i}.flac", format="Flac", size=1024**3) for i in range(5)]
    items = [_item(f"i{i}", files=[f]) for i, f in enumerate(files)]
    client = FakeClient(items)
    main(["run", "--destdir", str(tmp_path), "--size-budget", "2"], client=client)
    assert len(client.downloaded) <= 3


def test_e2e_dry_run_writes_nothing(tmp_path, capsys):
    client = FakeClient([_item()])
    code = main(["run", "--destdir", str(tmp_path), "--dry-run"], client=client)
    assert code == 0
    assert client.downloaded == []
    assert not (tmp_path / "manifest.jsonl").exists()


# --- manifest end-to-end: run scrive, export-manifest converte ---


def test_e2e_run_then_export_manifest(tmp_path, capsys):
    client = FakeClient([_item()])
    main(["run", "--destdir", str(tmp_path)], client=client)
    manifest = tmp_path / "manifest.jsonl"
    assert manifest.exists()

    csv_out = tmp_path / "report.csv"
    code = main(["export-manifest", str(manifest), "-o", str(csv_out)])
    assert code == 0
    assert "Esportate 1 righe" in capsys.readouterr().out
    assert "downloaded" in csv_out.read_text(encoding="utf-8")


def test_e2e_run_with_job_yaml_and_flag_override(tmp_path):
    job = tmp_path / "job.yaml"
    job.write_text(
        "search:\n  max_items: 1\nfiles:\n  formats: [Flac]\n", encoding="utf-8"
    )
    files = [
        IAFile(name="a.flac", format="Flac", size=1),
        IAFile(name="a.mp3", format="VBR MP3", size=1),
    ]
    client = FakeClient([_item(files=files)])
    main(["run", str(job), "--destdir", str(tmp_path)], client=client)
    assert client.downloaded == ["a.flac"]  # formats:[Flac] dal job


def test_e2e_profiles_command_lists_all(capsys):
    assert main(["profiles"]) == 0
    out = capsys.readouterr().out
    assert {"corpus", "dataset", "mirror"} <= set(out.split())


@pytest.mark.parametrize("bad", ["--layout=bogus", "--resume=nope"])
def test_e2e_invalid_choice_is_rejected(bad, tmp_path):
    with pytest.raises(SystemExit):
        main(["run", "--destdir", str(tmp_path), bad])
