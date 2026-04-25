import json
import os
from dataclasses import dataclass, asdict


@dataclass
class AppConfig:
    device_name: str = "REG1K0100A2 充电模块"
    voltage_max: float = 1000.0
    voltage_min: float = 150.0
    current_max: float = 100.0
    current_min: float = 0.0
    default_group: int = 1
    group_range_max: int = 15
    module_pending_timeout_ms: int = 3000
    module_offline_timeout_ms: int = 10000
    module_gone_timeout_ms: int = 30000
    poll_interval_ms: int = 100
    group_discover_timeout_ms: int = 600


class ConfigManager:
    def __init__(self, config_path: str = "config.json"):
        self._path = config_path

    def load(self) -> AppConfig:
        if not os.path.exists(self._path):
            default = AppConfig()
            try:
                with open(self._path, 'w', encoding='utf-8') as f:
                    json.dump(asdict(default), f, ensure_ascii=False, indent=2)
            except OSError:
                pass
            return default
        try:
            with open(self._path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            d = AppConfig()
            return AppConfig(
                device_name=data.get("device_name", d.device_name),
                voltage_max=float(data.get("voltage_max", d.voltage_max)),
                voltage_min=float(data.get("voltage_min", d.voltage_min)),
                current_max=float(data.get("current_max", d.current_max)),
                current_min=float(data.get("current_min", d.current_min)),
                default_group=int(data.get("default_group", d.default_group)),
                group_range_max=int(data.get("group_range_max", d.group_range_max)),
                module_pending_timeout_ms=int(data.get("module_pending_timeout_ms", d.module_pending_timeout_ms)),
                module_offline_timeout_ms=int(data.get("module_offline_timeout_ms", d.module_offline_timeout_ms)),
                module_gone_timeout_ms=int(data.get("module_gone_timeout_ms", d.module_gone_timeout_ms)),
                poll_interval_ms=int(data.get("poll_interval_ms", d.poll_interval_ms)),
                group_discover_timeout_ms=int(data.get("group_discover_timeout_ms", d.group_discover_timeout_ms)),
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return AppConfig()
