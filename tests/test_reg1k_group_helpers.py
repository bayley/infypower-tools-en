import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class _MockCAN:
    def __init__(self):
        self.sent = []   # list of (can_id, bytes)

    def send_data_ch1(self, can_id, data):
        self.sent.append((can_id, bytes(data)))
        return 1


@pytest.fixture
def mock_can(monkeypatch):
    import REG1K0100A2
    mc = _MockCAN()
    REG1K0100A2.REGx_Init(mc)
    monkeypatch.setattr(REG1K0100A2, 'g_log_callback', None)
    return mc


def test_group_set_output_encodes_identifier(mock_can):
    from REG1K0100A2 import REGx_GroupSetOutput
    REGx_GroupSetOutput(group_id=2, volt=512.0, total_curr=40.0)
    can_id, data = mock_can.sent[-1]
    # 02 DB 02 F0 — cmd=0x1B(101 1), device=0x0B(1011), dst=0x02, src=0xF0
    assert can_id == 0x02DB02F0
    # voltage = 512.0V → 512000 mV = 0x0007D000
    assert data[0:4] == bytes([0x00, 0x07, 0xD0, 0x00])
    # current = 40.0A → 40000 mA = 0x00009C40
    assert data[4:8] == bytes([0x00, 0x00, 0x9C, 0x40])


def test_group_launch_encodes_identifier(mock_can):
    from REG1K0100A2 import REGx_GroupLaunch
    REGx_GroupLaunch(group_id=3)
    can_id, data = mock_can.sent[-1]
    # cmd=0x1A, device=0x0B, dst=0x03, src=0xF0
    assert can_id == 0x02DA03F0
    assert data[0] == 0x00


def test_group_close_encodes_identifier(mock_can):
    from REG1K0100A2 import REGx_GroupClose
    REGx_GroupClose(group_id=3)
    can_id, data = mock_can.sent[-1]
    assert can_id == 0x02DA03F0
    assert data[0] == 0x01


def test_group_read_volt_curr_encodes_identifier(mock_can):
    from REG1K0100A2 import REGx_GroupReadVoltCurr
    REGx_GroupReadVoltCurr(group_id=1)
    can_id, _ = mock_can.sent[-1]
    # cmd=0x08, device=0x0B, dst=0x01, src=0xF0
    assert can_id == 0x02C801F0


def test_group_discover_modules_encodes_identifier(mock_can):
    from REG1K0100A2 import REGx_GroupReadModulesStatus
    REGx_GroupReadModulesStatus(group_id=1)
    can_id, _ = mock_can.sent[-1]
    # cmd=0x04, device=0x0B, dst=0x01, src=0xF0
    assert can_id == 0x02C401F0
