# -*- coding: utf-8 -*-
"""Engelsiz Mail otomatik testlerinde ortak kullanılan yardımcı araçlar."""

from .environment import TemporaryWorkspace, temporary_database, temporary_workspace
from .fakes import (
    FakeControl,
    FakeIMAP,
    FakeIdleContext,
    FakeNVDASink,
    FakeSMTPFactory,
    FakeSMTPSession,
    FakeTimer,
    FakeWx,
    nvda_module_stubs,
)
from .module_loader import MAIL_ROOT, PROJECT_ROOT, isolated_modules, load_mail_module, module

__all__ = [
    "FakeControl",
    "FakeIMAP",
    "FakeIdleContext",
    "FakeNVDASink",
    "FakeSMTPFactory",
    "FakeSMTPSession",
    "FakeTimer",
    "FakeWx",
    "MAIL_ROOT",
    "PROJECT_ROOT",
    "TemporaryWorkspace",
    "isolated_modules",
    "load_mail_module",
    "module",
    "nvda_module_stubs",
    "temporary_database",
    "temporary_workspace",
]
