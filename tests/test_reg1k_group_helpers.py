import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_group_set_output_encodes_identifier(mock_can):
    from REG1K0100A2 import REGx_GroupSetOutput
    REGx_GroupSetOutput(group_id=2, volt=512.0, total_curr=40.0)
    can_id, data = mock_can.sent[-1]
    assert can_id == 0x02DB02F0
    assert data[0:4] == bytes([0x00, 0x07, 0xD0, 0x00])
    assert data[4:8] == bytes([0x00, 0x00, 0x9C, 0x40])


def test_group_launch_encodes_identifier(mock_can):
    from REG1K0100A2 import REGx_GroupLaunch
    REGx_GroupLaunch(group_id=3)
    can_id, data = mock_can.sent[-1]
    assert can_id == 0x02DA03F0
    assert data[0] == 0x00
    assert data[1:] == bytes(7)


def test_group_close_encodes_identifier(mock_can):
    from REG1K0100A2 import REGx_GroupClose
    REGx_GroupClose(group_id=3)
    can_id, data = mock_can.sent[-1]
    assert can_id == 0x02DA03F0
    assert data[0] == 0x01
    assert data[1:] == bytes(7)


def test_group_read_volt_curr_encodes_identifier(mock_can):
    from REG1K0100A2 import REGx_GroupReadVoltCurr
    REGx_GroupReadVoltCurr(group_id=1)
    can_id, data = mock_can.sent[-1]
    assert can_id == 0x02C801F0
    assert data == bytes(8)


def test_group_discover_modules_encodes_identifier(mock_can):
    from REG1K0100A2 import REGx_GroupReadModulesStatus
    REGx_GroupReadModulesStatus(group_id=1)
    can_id, data = mock_can.sent[-1]
    assert can_id == 0x02C401F0
    assert data == bytes(8)
