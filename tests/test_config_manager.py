import json
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_load_creates_default_file_when_missing(tmp_path):
    from config_manager import ConfigManager, AppConfig
    cfg_path = tmp_path / "config.json"
    mgr = ConfigManager(config_path=str(cfg_path))
    result = mgr.load()

    assert isinstance(result, AppConfig)
    assert result.device_name == "REG1K0100A2 充电模块"
    assert result.voltage_max == 1000.0
    assert result.voltage_min == 150.0
    assert result.current_max == 100.0
    assert result.current_min == 0.0
    assert cfg_path.exists()


def test_load_reads_existing_file(tmp_path):
    from config_manager import ConfigManager, AppConfig
    cfg_path = tmp_path / "config.json"
    data = {
        "device_name": "测试电源",
        "voltage_max": 750.0,
        "voltage_min": 100.0,
        "current_max": 50.0,
        "current_min": 0.0,
    }
    cfg_path.write_text(json.dumps(data), encoding='utf-8')
    mgr = ConfigManager(config_path=str(cfg_path))
    result = mgr.load()

    assert result.device_name == "测试电源"
    assert result.voltage_max == 750.0
    assert result.current_max == 50.0


def test_load_returns_defaults_on_corrupt_file(tmp_path):
    from config_manager import ConfigManager, AppConfig
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text("not valid json", encoding='utf-8')
    mgr = ConfigManager(config_path=str(cfg_path))
    result = mgr.load()

    assert result.device_name == "REG1K0100A2 充电模块"


def test_load_returns_new_default_fields(tmp_path):
    from config_manager import ConfigManager
    cfg_path = tmp_path / "config.json"
    mgr = ConfigManager(config_path=str(cfg_path))
    result = mgr.load()

    assert result.default_group == 1
    assert result.group_range_max == 15
    assert result.module_pending_timeout_ms == 3000
    assert result.module_offline_timeout_ms == 10000
    assert result.module_gone_timeout_ms == 30000
    assert result.poll_interval_ms == 100
    assert result.group_discover_timeout_ms == 600


def test_load_falls_back_when_old_config_missing_new_fields(tmp_path):
    import json
    from config_manager import ConfigManager
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({
        "device_name": "old",
        "voltage_max": 800.0,
        "voltage_min": 100.0,
        "current_max": 50.0,
        "current_min": 0.0,
    }), encoding='utf-8')
    mgr = ConfigManager(config_path=str(cfg_path))
    result = mgr.load()

    assert result.device_name == "old"
    assert result.default_group == 1
    assert result.poll_interval_ms == 100


def test_load_reads_new_fields_from_file(tmp_path):
    import json
    from config_manager import ConfigManager
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({
        "default_group": 3,
        "group_range_max": 8,
        "module_pending_timeout_ms": 5000,
        "module_offline_timeout_ms": 20000,
        "module_gone_timeout_ms": 60000,
        "poll_interval_ms": 200,
        "group_discover_timeout_ms": 1200,
    }), encoding='utf-8')
    mgr = ConfigManager(config_path=str(cfg_path))
    result = mgr.load()

    assert result.default_group == 3
    assert result.group_range_max == 8
    assert result.module_pending_timeout_ms == 5000
    assert result.module_offline_timeout_ms == 20000
    assert result.module_gone_timeout_ms == 60000
    assert result.poll_interval_ms == 200
    assert result.group_discover_timeout_ms == 1200
