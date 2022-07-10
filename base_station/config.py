"""
Contains helper classes and default values for the configuration file
"""
import typing as t


class Config:
    def __init__(self, cfg: dict):
        self.server = ServerSection(cfg.get("server", {}))
        self.wss = WssSection(cfg.get("wss", {}))


class ServerSection:
    def __init__(self, cfg: dict):
        self.host = cfg.get("host", None)
        self.port = cfg.get("port", 11571)


class WssSection:
    def __init__(self, cfg: dict):
        self.enabled: bool = cfg.get("enabled", False)
        self.chain_path: str = cfg.get("chain_path", "chain.pem")
        self.privkey_path: str = cfg.get("privkey_path", "privkey.pem")
