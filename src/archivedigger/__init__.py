"""archivedigger — bulk audio downloader per Internet Archive.

Package pensato per l'uso sia come libreria (importato da altri repository)
sia come CLI (`archivedigger`).

Uso come libreria::

    from archivedigger import Config, dig
    report = dig(Config.build(profile="corpus", job=my_job))
"""

from .api import dig, search
from .config import Config
from .downloader import Downloader, DownloadReport
from .manifest import Manifest, ManifestRecord, export_csv

__version__ = "0.1.0"

__all__ = [
    "Config",
    "DownloadReport",
    "Downloader",
    "Manifest",
    "ManifestRecord",
    "dig",
    "export_csv",
    "search",
]
