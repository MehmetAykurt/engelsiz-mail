# -*- coding: utf-8 -*-
"""SMTP, IMAP, wxPython ve NVDA bağımlılıkları için ortak sahte nesneler."""

from __future__ import annotations

import collections
import smtplib as stdlib_smtplib
import types
from dataclasses import dataclass, field
from typing import Any

from .module_loader import module


class ScriptedFailureMixin:
    """Yöntem bazında bir veya birden çok sonuç/hata sıraya koyar."""

    def __init__(self) -> None:
        self._scripted_results: dict[str, collections.deque[Any]] = {}

    def script(self, method_name: str, *results_or_errors: Any) -> None:
        queue = self._scripted_results.setdefault(method_name, collections.deque())
        queue.extend(results_or_errors)

    def _scripted(self, method_name: str, default: Any = None) -> Any:
        queue = self._scripted_results.get(method_name)
        if not queue:
            return default
        result = queue.popleft()
        if isinstance(result, BaseException):
            raise result
        return result


class FakeSMTPSession(ScriptedFailureMixin):
    """Ağ kullanmadan SMTP oturum sırasını ve gönderilen iletileri kaydeder."""

    def __init__(self, host: str = "", port: int = 0, **options: Any) -> None:
        super().__init__()
        self.host = host
        self.port = port
        self.options = dict(options)
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.logged_in_as: tuple[str, str] | None = None
        self.sent_messages: list[dict[str, Any]] = []
        self.closed = False
        self.quit_called = False
        self.tls_started = False

    def _record(self, name: str, *args: Any, **kwargs: Any) -> None:
        self.calls.append((name, args, kwargs))

    def ehlo(self):
        self._record("ehlo")
        return self._scripted("ehlo", (250, b"OK"))

    def starttls(self, **kwargs):
        self._record("starttls", **kwargs)
        self.tls_started = True
        return self._scripted("starttls", (220, b"Ready"))

    def login(self, username: str, password: str):
        self._record("login", username, password)
        result = self._scripted("login", (235, b"Authenticated"))
        self.logged_in_as = (username, password)
        return result

    def send_message(self, message, *, from_addr=None, to_addrs=None, **kwargs):
        self._record(
            "send_message",
            message,
            from_addr=from_addr,
            to_addrs=list(to_addrs or []),
            **kwargs,
        )
        result = self._scripted("send_message", {})
        self.sent_messages.append(
            {
                "message": message,
                "from_addr": from_addr,
                "to_addrs": list(to_addrs or []),
            }
        )
        return result

    def quit(self):
        self._record("quit")
        result = self._scripted("quit", (221, b"Bye"))
        self.quit_called = True
        self.closed = True
        return result

    def close(self):
        self._record("close")
        self.closed = True
        return self._scripted("close", None)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False


class FakeSMTPFactory:
    """``SMTP_SSL`` ve ``SMTP`` kurucularını denetlenebilir oturumlara dönüştürür."""

    def __init__(self) -> None:
        self.ssl_sessions: list[FakeSMTPSession] = []
        self.starttls_sessions: list[FakeSMTPSession] = []
        self.ssl_constructor_results: collections.deque[Any] = collections.deque()
        self.starttls_constructor_results: collections.deque[Any] = collections.deque()

    @staticmethod
    def _construct(queue, sessions, host, port, options):
        if queue:
            configured = queue.popleft()
            if isinstance(configured, BaseException):
                raise configured
            session = configured
        else:
            session = FakeSMTPSession(host, port, **options)
        sessions.append(session)
        return session

    def SMTP_SSL(self, host="", port=0, **options):
        return self._construct(
            self.ssl_constructor_results,
            self.ssl_sessions,
            host,
            port,
            options,
        )

    def SMTP(self, host="", port=0, **options):
        return self._construct(
            self.starttls_constructor_results,
            self.starttls_sessions,
            host,
            port,
            options,
        )

    def as_module(self) -> types.ModuleType:
        return module(
            "mail.vendor.smtplib",
            SMTP_SSL=self.SMTP_SSL,
            SMTP=self.SMTP,
            SMTPException=stdlib_smtplib.SMTPException,
            SMTPAuthenticationError=stdlib_smtplib.SMTPAuthenticationError,
            SMTPRecipientsRefused=stdlib_smtplib.SMTPRecipientsRefused,
            SMTPSenderRefused=stdlib_smtplib.SMTPSenderRefused,
            SMTPDataError=stdlib_smtplib.SMTPDataError,
            SMTPNotSupportedError=stdlib_smtplib.SMTPNotSupportedError,
            SMTPServerDisconnected=stdlib_smtplib.SMTPServerDisconnected,
        )


class FakeIdleContext:
    def __init__(self, responses=None) -> None:
        self.responses = list(responses or [])
        self.burst_interval = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def __iter__(self):
        return iter(self.responses)

    def burst(self, interval=0.1):
        self.burst_interval = interval
        return iter(self.responses)


class FakeIMAP(ScriptedFailureMixin):
    """IMAP komutlarını kaydeden ve yanıtları yöntem bazında betikleyen istemci."""

    def __init__(self, host: str = "", port: int = 993, **options: Any) -> None:
        super().__init__()
        self.host = host
        self.port = port
        self.options = dict(options)
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.uid_responses: dict[str, Any] = {}
        self.selected_mailbox: str | None = None
        self.logged_in_as: tuple[str, str] | None = None
        self.shutdown_called = False
        self.logout_called = False
        self.idle_responses: list[Any] = []

    def _call(self, name: str, *args: Any) -> None:
        self.calls.append((name, args))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.logout()
        return False

    def login(self, username: str, password: str):
        self._call("login", username, password)
        result = self._scripted("login", ("OK", [b"Authenticated"]))
        self.logged_in_as = (username, password)
        return result

    def select(self, mailbox="INBOX", readonly=False):
        self._call("select", mailbox, readonly)
        result = self._scripted("select", ("OK", [b"0"]))
        self.selected_mailbox = mailbox
        return result

    def uid(self, command: str, *args: Any):
        normalized = str(command or "").upper()
        self._call("uid", normalized, *args)
        if normalized in self.uid_responses:
            result = self.uid_responses[normalized]
            if isinstance(result, BaseException):
                raise result
            if callable(result):
                return result(*args)
            return result
        return self._scripted(f"uid:{normalized}", ("OK", []))

    def status(self, mailbox, names):
        self._call("status", mailbox, names)
        return self._scripted("status", ("OK", [b"INBOX (MESSAGES 0 UNSEEN 0)"]))

    def list(self, *args):
        self._call("list", *args)
        return self._scripted("list", ("OK", []))

    def noop(self):
        self._call("noop")
        return self._scripted("noop", ("OK", [b""]))

    def response(self, code):
        self._call("response", code)
        return self._scripted(f"response:{code}", (None, [None]))

    def idle(self, *args, **kwargs):
        self._call("idle", *args)
        scripted = self._scripted("idle", None)
        return scripted if scripted is not None else FakeIdleContext(self.idle_responses)

    def shutdown(self):
        self._call("shutdown")
        self.shutdown_called = True
        return self._scripted("shutdown", None)

    def logout(self):
        self._call("logout")
        self.logout_called = True
        return self._scripted("logout", ("BYE", [b"Logout completed"]))


@dataclass
class FakeTimer:
    delay_ms: int
    callback: Any
    args: tuple[Any, ...]
    kwargs: dict[str, Any] = field(default_factory=dict)
    stopped: bool = False
    fired: bool = False

    def Stop(self):
        self.stopped = True

    def fire(self):
        if self.stopped:
            return None
        self.fired = True
        return self.callback(*self.args, **self.kwargs)


class FakeControl:
    def __init__(self, value: Any = "") -> None:
        self.value = value
        self.focused = False
        self.destroyed = False
        self.accessible_name = ""

    def SetFocus(self):
        self.focused = True

    def IsBeingDeleted(self):
        return self.destroyed

    def GetValue(self):
        return self.value

    def SetValue(self, value):
        self.value = value

    def SetName(self, name):
        self.accessible_name = str(name)


class FakeWx(types.ModuleType):
    """CallAfter/CallLater, odak ve temel sabitler için hafif wxPython taklidi."""

    def __init__(self, *, immediate_call_after: bool = True) -> None:
        super().__init__("wx")
        self.immediate_call_after = immediate_call_after
        self.call_after_queue: list[tuple[Any, tuple[Any, ...], dict[str, Any]]] = []
        self.timers: list[FakeTimer] = []
        self.messages: list[tuple[Any, ...]] = []
        self.bell_count = 0

        self.ID_OK = 5100
        self.ID_CANCEL = 5101
        self.YES = 2
        self.NO = 8
        self.OK = 4
        self.ICON_ERROR = 16
        self.ICON_WARNING = 32
        self.ICON_INFORMATION = 64
        self.FONTSTYLE_NORMAL = 0
        self.FONTSTYLE_ITALIC = 1
        self.FONTWEIGHT_NORMAL = 0
        self.FONTWEIGHT_BOLD = 1
        self.ListItem = object
        self.Window = FakeControl

    def CallAfter(self, callback, *args, **kwargs):
        self.call_after_queue.append((callback, args, kwargs))
        if self.immediate_call_after:
            return callback(*args, **kwargs)
        return None

    def run_call_after_queue(self):
        queued = list(self.call_after_queue)
        self.call_after_queue.clear()
        results = []
        for callback, args, kwargs in queued:
            results.append(callback(*args, **kwargs))
        return results

    def CallLater(self, delay_ms, callback, *args, **kwargs):
        timer = FakeTimer(int(delay_ms), callback, args, kwargs)
        self.timers.append(timer)
        return timer

    def MessageBox(self, *args, **kwargs):
        self.messages.append((*args, kwargs))
        return self.ID_OK

    def Bell(self):
        self.bell_count += 1


@dataclass
class FakeNVDASink:
    spoken_messages: list[str] = field(default_factory=list)

    def message(self, text):
        self.spoken_messages.append(str(text))


def nvda_module_stubs(config_path: str, *, wx_module: FakeWx | None = None):
    """Yaygın NVDA modüllerini tek sözlükte sağlar."""
    wx_module = wx_module or FakeWx()
    sink = FakeNVDASink()

    class GlobalPlugin:
        def __init__(self, *args, **kwargs):
            super().__init__()

        def terminate(self):
            return None

    stubs = {
        "wx": wx_module,
        "globalVars": module(
            "globalVars",
            appArgs=types.SimpleNamespace(configPath=str(config_path)),
        ),
        "globalPluginHandler": module(
            "globalPluginHandler",
            GlobalPlugin=GlobalPlugin,
        ),
        "ui": module("ui", message=sink.message),
        "gui": module("gui", mainFrame=FakeControl()),
        "api": module("api", getFocusObject=lambda: None),
    }
    return stubs, sink, wx_module
