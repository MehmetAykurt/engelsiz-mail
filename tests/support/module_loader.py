# -*- coding: utf-8 -*-
"""NVDA dışındaki testlerde Engelsiz Mail modüllerini yalıtılmış yükleme araçları."""

from __future__ import annotations

import contextlib
import importlib.util
import pathlib
import sys
import types
from collections.abc import Iterator, Mapping


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
MAIL_ROOT = PROJECT_ROOT / "globalPlugins" / "mail"


def module(name: str, **attributes) -> types.ModuleType:
    """Verilen üyelerle basit bir sahte Python modülü oluşturur."""
    result = types.ModuleType(name)
    for attribute_name, value in attributes.items():
        setattr(result, attribute_name, value)
    return result


def _mail_module_names() -> set[str]:
    return {
        name
        for name in sys.modules
        if name == "mail" or name.startswith("mail.")
    }


@contextlib.contextmanager
def isolated_modules(stubs: Mapping[str, object] | None = None) -> Iterator[None]:
    """``mail`` ad alanını ve verilen sahte modülleri işlemden sonra eksiksiz geri yükler."""
    stubs = dict(stubs or {})
    touched_names = _mail_module_names() | set(stubs)
    previous = {name: sys.modules.get(name) for name in touched_names}

    for name in _mail_module_names():
        sys.modules.pop(name, None)

    package = module("mail")
    package.__path__ = [str(MAIL_ROOT)]
    package.__package__ = "mail"
    sys.modules["mail"] = package
    for name, fake_module in stubs.items():
        sys.modules[name] = fake_module

    try:
        yield
    finally:
        current_names = _mail_module_names() | set(stubs)
        for name in current_names:
            sys.modules.pop(name, None)
        for name, old_value in previous.items():
            if old_value is not None:
                sys.modules[name] = old_value


@contextlib.contextmanager
def load_mail_module(
    relative_name: str,
    *,
    stubs: Mapping[str, object] | None = None,
) -> Iterator[types.ModuleType]:
    """Bir üretim modülünü gerçek paket yolundan, kontrollü bağımlılıklarla yükler.

    Örnek::

        with load_mail_module("validators") as validators:
            assert validators.eposta_adresi_gecerli_mi("a@example.com")
    """
    relative_name = str(relative_name or "").strip(".")
    if not relative_name:
        raise ValueError("Yüklenecek modül adı boş olamaz.")

    module_path = MAIL_ROOT.joinpath(*relative_name.split(".")).with_suffix(".py")
    if not module_path.is_file():
        package_init = MAIL_ROOT.joinpath(*relative_name.split("."), "__init__.py")
        if package_init.is_file():
            module_path = package_init
        else:
            raise FileNotFoundError(f"Engelsiz Mail modülü bulunamadı: {relative_name}")

    full_name = f"mail.{relative_name}"
    with isolated_modules(stubs):
        spec = importlib.util.spec_from_file_location(full_name, module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Modül yükleme tanımı oluşturulamadı: {full_name}")
        loaded = importlib.util.module_from_spec(spec)
        sys.modules[full_name] = loaded
        spec.loader.exec_module(loaded)
        yield loaded
