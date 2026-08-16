# -*- coding: utf-8 -*-
"""Geçici dosya sistemi, ayar dizini ve SQLite çalışma alanı yardımcıları."""

from __future__ import annotations

import contextlib
import pathlib
import sqlite3
import tempfile
from dataclasses import dataclass
from typing import Iterator

from .module_loader import load_mail_module, module


@dataclass(frozen=True)
class TemporaryWorkspace:
    root: pathlib.Path
    config_dir: pathlib.Path
    cache_dir: pathlib.Path
    attachment_dir: pathlib.Path
    database_path: pathlib.Path
    settings_path: pathlib.Path

    def file(self, relative_path: str, content: bytes | str = b"") -> pathlib.Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, str):
            path.write_text(content, encoding="utf-8")
        else:
            path.write_bytes(content)
        return path


@contextlib.contextmanager
def temporary_workspace(prefix: str = "engelsiz-mail-test-") -> Iterator[TemporaryWorkspace]:
    with tempfile.TemporaryDirectory(prefix=prefix) as directory:
        root = pathlib.Path(directory)
        config_dir = root / "config"
        cache_dir = root / "cache"
        attachment_dir = cache_dir / "attachments"
        for path in (config_dir, cache_dir, attachment_dir):
            path.mkdir(parents=True, exist_ok=True)
        yield TemporaryWorkspace(
            root=root,
            config_dir=config_dir,
            cache_dir=cache_dir,
            attachment_dir=attachment_dir,
            database_path=cache_dir / "mail.db",
            settings_path=config_dir / "settings.json",
        )


@contextlib.contextmanager
def temporary_database():
    """Gerçek göçleri kullanan, tamamen geçici Engelsiz Mail veritabanı sağlar."""
    with temporary_workspace() as workspace:
        logger = module(
            "mail.logger",
            hata_kaydet=lambda *args, **kwargs: None,
            uyari_kaydet=lambda *args, **kwargs: None,
        )
        paths = module(
            "mail.paths",
            AYARLAR_KLASORU=str(workspace.config_dir),
            AYARLAR_DOSYASI=str(workspace.settings_path),
            VERITABANI_DOSYASI=str(workspace.database_path),
            EKLER_KLASORU=str(workspace.attachment_dir),
        )
        sqlite_compat = module("mail.sqlite_compat", sqlite3=sqlite3)
        stubs = {
            "mail.logger": logger,
            "mail.paths": paths,
            "mail.sqlite_compat": sqlite_compat,
        }
        with load_mail_module("database", stubs=stubs) as database:
            database.veritabani_hazirla(str(workspace.database_path))
            yield database, workspace
