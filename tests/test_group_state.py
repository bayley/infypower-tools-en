import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_module_lifecycle_online_when_recently_seen():
    from group_state import ModuleState
    m = ModuleState(addr=0x00, last_seen=100.0)
    assert m.lifecycle(now=100.5, pending_ms=3000, offline_ms=10000, gone_ms=30000) == 'online'


def test_module_lifecycle_pending_after_pending_threshold():
    from group_state import ModuleState
    m = ModuleState(addr=0x00, last_seen=100.0)
    assert m.lifecycle(now=104.0, pending_ms=3000, offline_ms=10000, gone_ms=30000) == 'pending'


def test_module_lifecycle_offline_after_offline_threshold():
    from group_state import ModuleState
    m = ModuleState(addr=0x00, last_seen=100.0)
    assert m.lifecycle(now=115.0, pending_ms=3000, offline_ms=10000, gone_ms=30000) == 'offline'


def test_module_lifecycle_gone_after_gone_threshold():
    from group_state import ModuleState
    m = ModuleState(addr=0x00, last_seen=100.0)
    assert m.lifecycle(now=140.0, pending_ms=3000, offline_ms=10000, gone_ms=30000) == 'gone'
