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


def test_module_alarms_empty_when_no_bits_set():
    from group_state import ModuleState
    m = ModuleState(addr=0x00, status0=0, status1=0, status2=0, status3=0)
    assert m.alarms == []


def test_module_alarms_decodes_status0_bits():
    from group_state import ModuleState
    m = ModuleState(addr=0x00,
                    status0=(1 << 7) | (1 << 6) | (1 << 5) | (1 << 3))
    s = m.alarms
    assert "通讯中断告警" in s
    assert "风道不畅" in s
    assert "模块放电异常" in s
    assert "输入或母线异常" in s


def test_module_alarms_skips_sleeping_bit():
    from group_state import ModuleState
    m = ModuleState(addr=0x00, status0=(1 << 4))
    assert m.alarms == []
    assert m.sleeping is True


def test_module_alarms_decodes_status1_bits():
    from group_state import ModuleState
    m = ModuleState(addr=0x00, status1=(1 << 4) | (1 << 1))
    assert "过温告警" in m.alarms
    assert "模块故障告警" in m.alarms


def test_module_alarms_decodes_status2_bits():
    from group_state import ModuleState
    m = ModuleState(addr=0x00, status2=(1 << 7) | (1 << 6))
    assert "模块PFC侧处于关机状态" in m.alarms
    assert "输入过压告警" in m.alarms


def test_module_alarms_skips_walkin_bit():
    from group_state import ModuleState
    m = ModuleState(addr=0x00, status1=(1 << 6))
    assert m.alarms == []


def test_group_state_total_power_is_voltage_times_current():
    from group_state import GroupState
    g = GroupState(group_id=1, voltage=500.0, total_current=20.0)
    assert g.total_power == 10000.0


def test_group_state_total_power_is_zero_when_voltage_zero():
    from group_state import GroupState
    g = GroupState(group_id=1, voltage=0.0, total_current=20.0)
    assert g.total_power == 0.0


def test_group_state_is_on_when_voltage_above_threshold():
    from group_state import GroupState
    g = GroupState(group_id=1, voltage=10.0)
    assert g.is_on is True


def test_group_state_is_off_when_voltage_below_threshold():
    from group_state import GroupState
    g = GroupState(group_id=1, voltage=2.0)
    assert g.is_on is False


def test_group_state_modules_starts_empty():
    from group_state import GroupState
    g = GroupState(group_id=2)
    assert g.modules == {}
    assert g.module_count == 0


def test_group_state_module_count_reflects_dict():
    from group_state import GroupState, ModuleState
    g = GroupState(group_id=2)
    g.modules[0x00] = ModuleState(addr=0x00)
    g.modules[0x01] = ModuleState(addr=0x01)
    assert g.module_count == 2


def test_group_state_is_off_at_exact_threshold_voltage():
    from group_state import GroupState
    g = GroupState(group_id=1, voltage=5.0)
    assert g.is_on is False  # > not >=, exactly 5V 视为关机
