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
        self.server = ServerSection(cfg.get("server", {}))
        self.wss = WssSection(cfg.get("wss", {}))
        self.auth = AuthSection(cfg.get("auth", {}))
        self.data = DataSection(cfg.get("data", {}))
        self.logging = LoggingSection(cfg.get("logging", {}))


class ServerSection:
    def __init__(self, cfg: dict):
        self.host = cfg.get("host", None)
        self.port = cfg.get("port", 11571)


class WssSection:
    def __init__(self, cfg: dict):
        self.enabled: bool = cfg.get("enabled", False)
        self.chain_path: str = cfg.get("chain_path", "chain.pem")
        self.privkey_path: str = cfg.get("privkey_path", "privkey.pem")


class AuthSection:
    def __init__(self, cfg: dict):
        self.require_auth: bool = cfg.get("require_auth", True)
        self.userbase_path: str = cfg.get("userbase_path", "rover_users.json")
        self.paths: dict = cfg.get("paths", {
            "/driver": "driver",
            "/rover": "rover"
        })
        self.limits: dict = cfg.get("limits", {})


class DataSection:
    def __init__(self, cfg: dict):
        self.enabled: bool = cfg.get("enabled", False)
        self.influx_host: str = cfg.get("influx_host", "localhost")
        self.influx_port: int = cfg.get("influx_post", 8086)
        self.influx_user: str = cfg.get("influx_user", "root")
        self.influx_pass: str = cfg.get("influx_port", "root")
        self.influx_db: str = cfg.get("influx_db", "landsharks_rover")


class LoggingSection:
    def __init__(self, cfg: dict):
        self.enabled: bool = cfg.get("enabled", True)
        self.format: str = cfg.get("format", "{asctime} [{levelname}] [{name}: {module}.{funcName}] {message}")
        self.format_style: str = cfg.get("format_style", "{")
        self.main_logger = MainLoggerEntry(cfg.get("main_logger", {}))
        self.extra_loggers = {k: LOG_LEVELS[v] for k, v in cfg.get("extra_loggers", {}).items()}
        self.handlers = HandlersEntry(cfg.get("handlers", {}))


class MainLoggerEntry:
    def __init__(self, cfg: dict):
        self.name: str = cfg.get("name", "base_station")
        self.level: int = LOG_LEVELS[cfg.get("level", "debug").lower()]


class HandlersEntry:
    def __init__(self, cfg: dict):
        self.stream = StreamHandlerEntry(cfg.get("stream", {}))
        self.file = FileHandlerEntry(cfg.get("file", {}))


class StreamHandlerEntry:
    def __init__(self, cfg: dict):
        self.enabled: bool = cfg.get("enabled", False)
        self.level: int = LOG_LEVELS[cfg.get("level", "debug").lower()]

        self.stream: t.TextIO = _STREAMS.get(cfg.get("stream", "stderr"))


class FileHandlerEntry:
    def __init__(self, cfg: dict):
        self.enabled: bool = cfg.get("enabled", False)
        self.level: int = LOG_LEVELS[cfg.get("level", "debug").lower()]
        self.path: str = cfg.get("path", "logs/base_station.log")
        self.rotate: bool = cfg.get("rotate", False)
        self.rotate_when: str = cfg.get("rotate_when", "midnight")
        self.rotate_interval: int = cfg.get("rotate_interval", 1)
