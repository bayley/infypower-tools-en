import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class _FakeMsg:
    def __init__(self, can_id, data):
        self.can_id = can_id
        self.data = bytes(data)


def test_register_listener_called_with_rx_event():
    import REG1K0100A2
    REG1K0100A2._rx_listeners.clear()
    captured = []
    REG1K0100A2.REGx_RegisterListener(lambda ev: captured.append(ev))

    msg = _FakeMsg(0x0289F000,  # cmd=0x09, device=0x0A, dst=0xF0, src=0x00
                   bytes([0, 3, 0x0D, 0x40, 0, 0, 0x13, 0x88]))
    info = REG1K0100A2.CANControllerInfo()
    REG1K0100A2.REGx_CAN_ReceviceCallback(msg, info)

    assert len(captured) == 1
    ev = captured[0]
    assert ev.cmdCode == 0x09
    assert ev.deviceCode == 0x0A
    assert ev.dstAddr == 0xF0
    assert ev.srcAddr == 0x00
    assert ev.data[:8] == bytes([0, 3, 0x0D, 0x40, 0, 0, 0x13, 0x88])


def test_legacy_listener_still_fills_canController_info():
    """确保旧路径（CANControllerInfo）不被打断 — manual_widget 还在用"""
    import REG1K0100A2
    REG1K0100A2._rx_listeners.clear()
    info = REG1K0100A2.CANControllerInfo()
    msg = _FakeMsg(0x0289F000,
                   bytes([0, 3, 0x0D, 0x40, 0, 0, 0x13, 0x88]))
    REG1K0100A2.REGx_CAN_ReceviceCallback(msg, info)

    assert info.DC_Output_Volt == pytest.approx(200.0)
    assert info.DC_Output_Curr == pytest.approx(5.0)


def test_unregister_listener():
    import REG1K0100A2
    REG1K0100A2._rx_listeners.clear()
    captured = []
    cb = lambda ev: captured.append(ev)
    REG1K0100A2.REGx_RegisterListener(cb)
    REG1K0100A2.REGx_UnregisterListener(cb)

    msg = _FakeMsg(0x0289F000, bytes(8))
    info = REG1K0100A2.CANControllerInfo()
    REG1K0100A2.REGx_CAN_ReceviceCallback(msg, info)
    assert captured == []


def test_exception_in_listener_does_not_abort_next():
    import REG1K0100A2
    REG1K0100A2._rx_listeners.clear()

    def _boom(ev):
        raise RuntimeError("boom")

    captured = []
    REG1K0100A2.REGx_RegisterListener(_boom)
    REG1K0100A2.REGx_RegisterListener(lambda ev: captured.append(ev))

    msg = _FakeMsg(0x0289F000, bytes([0, 3, 0x0D, 0x40, 0, 0, 0x13, 0x88]))
    info = REG1K0100A2.CANControllerInfo()
    REG1K0100A2.REGx_CAN_ReceviceCallback(msg, info)

    assert len(captured) == 1  # second listener still ran
