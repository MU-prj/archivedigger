"""Test della CLI: mappatura flag -> override di Config e dispatch comandi."""

from archivedigger.cli import args_to_overrides, config_from_args, main, parse_args
from archivedigger.models import IAFile, IAItem


def _overrides(argv):
    return args_to_overrides(parse_args(["run", *argv]))


class FakeClient:
    def __init__(self, items):
        self._items = {it.identifier: it for it in items}
        self.downloaded = []

    def search(self, query, sort="downloads desc", max_items=100):
        return iter(list(self._items)[: max_items or None])

    def get_item(self, identifier):
        return self._items[identifier]

    def download_file(self, item, file, local_path):
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(b"x")
        self.downloaded.append(file.name)


def _item():
    return IAItem(
        identifier="show1",
        metadata={"collection": "jazz"},
        files=[IAFile(name="a.flac", format="Flac", size=1)],
    )


def test_workers_flag_maps_to_download_override():
    assert _overrides(["--workers", "8"]) == {"download": {"workers": 8}}


def test_repeatable_collection_flag_builds_list():
    ov = _overrides(["--collection", "a", "--collection", "b"])
    assert ov["search"]["collection"] == ["a", "b"]


def test_prefer_flag_is_parsed_into_groups():
    ov = _overrides(["--prefer", "Flac=AIFF=WAVE>VBR MP3"])
    assert ov["files"]["prefer"] == [["Flac", "AIFF", "WAVE"], ["VBR MP3"]]


def test_prefer_skips_empty_groups():
    from archivedigger.cli import parse_prefer

    # separatori spuri (gruppi vuoti) vengono ignorati, non producono [[]]
    assert parse_prefer("Flac>>VBR MP3>") == [["Flac"], ["VBR MP3"]]


def test_boolean_flags():
    ov = _overrides(["--dry-run", "--dedup"])
    assert ov["download"]["dry_run"] is True
    assert ov["filters"]["dedup"] is True


def test_flat_and_force_map_to_layout_and_resume():
    ov = _overrides(["--flat", "--force"])
    assert ov["download"]["layout"] == "flat"
    assert ov["download"]["resume"] == "force"


def test_no_ignore_errors_flag():
    ov = _overrides(["--no-ignore-errors"])
    assert ov["download"]["ignore_errors"] is False


def test_no_dedup_flag_can_turn_off_profile_dedup():
    # i profili corpus/dataset accendono dedup: la CLI deve poterlo spegnere
    ov = _overrides(["--no-dedup"])
    assert ov["filters"]["dedup"] is False


def test_alias_and_extended_flag_last_one_wins():
    # --flat e --layout condividono la dest: vince l'ultima flag scritta
    assert _overrides(["--flat", "--layout", "item"])["download"]["layout"] == "item"
    assert _overrides(["--layout", "item", "--flat"])["download"]["layout"] == "flat"
    assert _overrides(["--force", "--resume", "checksum"])["download"]["resume"] == "checksum"


def test_unset_flags_do_not_appear():
    assert _overrides([]) == {}


def test_flag_overrides_job_yaml(tmp_path):
    job = tmp_path / "job.yaml"
    job.write_text("download:\n  workers: 2\n", encoding="utf-8")
    args = parse_args(["run", str(job), "--workers", "9"])
    cfg = config_from_args(args)
    assert cfg.download.workers == 9


def test_profile_flag_selects_preset():
    args = parse_args(["run", "--profile", "dataset"])
    cfg = config_from_args(args)
    assert cfg.search.max_items == 1000  # dataset.yaml


def test_profile_flag_beats_job_profile_and_labels_config(tmp_path):
    # il profile del job non deve sopravvivere come etichetta quando la
    # flag --profile carica un preset diverso
    job = tmp_path / "job.yaml"
    job.write_text("profile: corpus\n", encoding="utf-8")
    cfg = config_from_args(parse_args(["run", str(job), "--profile", "dataset"]))
    assert cfg.profile == "dataset"
    assert cfg.search.max_items == 1000  # dataset.yaml, non corpus


def test_main_run_downloads_with_injected_client(tmp_path):
    client = FakeClient([_item()])
    code = main(["run", "--destdir", str(tmp_path)], client=client)
    assert code == 0
    assert client.downloaded == ["a.flac"]


def test_main_run_with_errors_exits_nonzero(tmp_path):
    class ExplodingClient(FakeClient):
        def download_file(self, item, file, local_path):
            raise OSError("network down")

    client = ExplodingClient([_item()])
    code = main(["run", "--destdir", str(tmp_path), "--retries", "0"], client=client)
    assert code == 1  # cron/CI devono vedere il fallimento


def test_main_search_lists_identifiers(capsys):
    client = FakeClient([_item()])
    code = main(["search"], client=client)
    assert code == 0
    assert "show1" in capsys.readouterr().out


def test_main_profiles_lists_presets(capsys):
    code = main(["profiles"])
    assert code == 0
    out = capsys.readouterr().out
    assert "corpus" in out and "dataset" in out and "mirror" in out


def test_main_export_manifest(tmp_path, capsys):
    from archivedigger.manifest import Manifest, ManifestRecord

    jsonl = tmp_path / "m.jsonl"
    Manifest(jsonl).append(ManifestRecord(identifier="i1", file="a.flac"))
    csv_out = tmp_path / "out.csv"
    code = main(["export-manifest", str(jsonl), "-o", str(csv_out)])
    assert code == 0
    assert csv_out.exists()
