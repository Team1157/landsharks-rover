"""
Contains helper classes and default values for the configuration file
"""
import sys
import typing as t
from base_station.util import LOG_LEVELS

_STREAMS = {
    "stdout": sys.stdout,
    "stderr": sys.stderr
}


class Config:
    def __init__(self, cfg: dict):
        self.server = ServerSection(cfg.get("server") or {})
        self.wss = WssSection(cfg.get("wss") or {})
        self.auth = AuthSection(cfg.get("auth") or {})
        self.data = DataSection(cfg.get("data") or {})
        self.logging = LoggingSection(cfg.get("logging") or {})


class ServerSection:
    def __init__(self, cfg: dict):
        self.host = cfg.get("host") or None
        self.port = cfg.get("port") or 11571


class WssSection:
    def __init__(self, cfg: dict):
        self.enabled: bool = cfg.get("enabled") or False
        self.chain_path: str = cfg.get("chain_path") or "chain.pem"
        self.privkey_path: str = cfg.get("privkey_path") or "privkey.pem"


class AuthSection:
    def __init__(self, cfg: dict):
        self.require_auth: bool = cfg.get("require_auth")
        if self.require_auth is None:
            self.require_auth = True
        self.userbase_path: str = cfg.get("userbase_path") or "rover_users.json"
        self.paths: dict = cfg.get("paths") or {}
        self.limits: dict = cfg.get("limits") or {}


class DataSection:
    def __init__(self, cfg: dict):
        self.enabled: bool = cfg.get("enabled") or False
        self.influx_host: str = cfg.get("influx_host") or "localhost"
        self.influx_port: int = cfg.get("influx_post") or 8086
        self.influx_user: str = cfg.get("influx_user") or "root"
        self.influx_pass: str = cfg.get("influx_port") or "root"
        self.influx_db: str = cfg.get("influx_db") or "landsharks_rover"


class LoggingSection:
    def __init__(self, cfg: dict):
        self.enabled: bool = cfg.get("enabled")
        if self.enabled is None:
            self.enabled = True
        self.format: str = cfg.get("format") or "{asctime} [{levelname}] [{name}: {module}.{funcName}] {message}"
        self.format_style: str = cfg.get("format_style") or "{"
        self.main_logger = MainLoggerEntry(cfg.get("main_logger") or {})
        self.extra_loggers = {k: LOG_LEVELS[v] for k, v in (cfg.get("extra_loggers") or {}).items()}
        self.handlers = HandlersEntry(cfg.get("handlers") or {})


class MainLoggerEntry:
    def __init__(self, cfg: dict):
        self.name: str = cfg.get("name") or "base_station"
        self.level: int = LOG_LEVELS[(cfg.get("level") or "debug").lower()]


class HandlersEntry:
    def __init__(self, cfg: dict):
        self.stream = StreamHandlerEntry(cfg.get("stream") or {})
        self.file = FileHandlerEntry(cfg.get("file") or {})


class StreamHandlerEntry:
    def __init__(self, cfg: dict):
        self.enabled: bool = cfg.get("enabled") or False
        self.level: int = LOG_LEVELS[(cfg.get("level") or "debug").lower()]

        self.stream: t.TextIO = _STREAMS.get(cfg.get("stream") or "stderr")


class FileHandlerEntry:
    def __init__(self, cfg: dict):
        self.enabled: bool = cfg.get("enabled") or False
        self.level: int = LOG_LEVELS[(cfg.get("level") or "debug").lower()]
        self.path: str = cfg.get("path") or "logs/base_station.log"
        self.rotate: bool = cfg.get("rotate") or False
        self.rotate_when: str = cfg.get("rotate_when") or "midnight"
        self.rotate_interval: int = cfg.get("rotate_interval") or 1
