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


def test_module_lifecycle_at_exact_pending_boundary():
    from group_state import ModuleState
    m = ModuleState(addr=0x00, last_seen=100.0)
    # elapsed_ms == pending_ms exactly → transitions to 'pending'
    assert m.lifecycle(now=103.0, pending_ms=3000, offline_ms=10000, gone_ms=30000) == 'pending'


def test_module_lifecycle_at_exact_offline_boundary():
    from group_state import ModuleState
    m = ModuleState(addr=0x00, last_seen=100.0)
    assert m.lifecycle(now=110.0, pending_ms=3000, offline_ms=10000, gone_ms=30000) == 'offline'


def test_module_lifecycle_at_exact_gone_boundary():
    from group_state import ModuleState
    m = ModuleState(addr=0x00, last_seen=100.0)
    assert m.lifecycle(now=130.0, pending_ms=3000, offline_ms=10000, gone_ms=30000) == 'gone'


def test_module_sleeping_true_when_status0_bit4_set():
    from group_state import ModuleState
    m = ModuleState(addr=0x00, status0=(1 << 4))
    assert m.sleeping is True


def test_module_sleeping_false_when_status0_bit4_clear():
    from group_state import ModuleState
    m = ModuleState(addr=0x00, status0=0)
    assert m.sleeping is False
