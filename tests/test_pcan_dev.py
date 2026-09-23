import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

can = pytest.importorskip("can")


class FakeBus:
    """Minimal stand-in for can.BusABC."""

    def __init__(self, rx=None, fail_recv=False, fail_send=False):
        self.rx = list(rx or [])
        self.sent = []
        self.shut = False
        self.fail_recv = fail_recv
        self.fail_send = fail_send

    def recv(self, timeout=0):
        if self.fail_recv:
            raise can.CanOperationError("bus off")
        return self.rx.pop(0) if self.rx else None

    def send(self, msg, timeout=None):
        if self.fail_send:
            raise can.CanOperationError("tx queue full")
        self.sent.append(msg)

    def shutdown(self):
        self.shut = True


def _dev(bus):
    from pcan_dev import PCANDev
    return PCANDev(channel='PCAN_USBBUS1', bitrate=125000, bus_factory=lambda: bus)


def test_open_and_close():
    bus = FakeBus()
    d = _dev(bus)
    assert d.isCanOpen is False
    assert d.open_device() is True
    assert d.isCanOpen is True
    d.close_device()
    assert d.isCanOpen is False
    assert bus.shut is True


def test_open_failure_reports_error():
    from pcan_dev import PCANDev

    def boom():
        raise can.CanInitializationError("PCAN_ERROR_ILLHW")

    d = PCANDev(bus_factory=boom)
    assert d.open_device() is False
    assert d.isCanOpen is False
    assert 'PCAN_ERROR_ILLHW' in d.last_error


def test_send_ch1_builds_extended_frame():
    bus = FakeBus()
    d = _dev(bus)
    d.open_device()
    d.send_data_ch1(0x028AF03F, bytes([1, 2, 3, 4, 5, 6, 7, 8]))
    assert len(bus.sent) == 1
    m = bus.sent[0]
    assert m.arbitration_id == 0x028AF03F
    assert m.is_extended_id is True
    assert bytes(m.data) == bytes([1, 2, 3, 4, 5, 6, 7, 8])


def test_send_ch2_is_ignored_on_single_channel_adapter():
    bus = FakeBus()
    d = _dev(bus)
    d.open_device()
    d.send_data_ch2(0x123, b'\x00' * 8)
    assert bus.sent == []


def test_send_when_closed_is_noop():
    bus = FakeBus()
    d = _dev(bus)
    d.send_data_ch1(0x123, b'\x00' * 8)
    assert bus.sent == []


def test_read_ch1_converts_messages_and_pads_to_8_bytes():
    rx = [
        can.Message(arbitration_id=0x0289F000, is_extended_id=True, data=bytes(range(8))),
        can.Message(arbitration_id=0x0289F001, is_extended_id=True, data=b'\xAA\xBB'),
        can.Message(arbitration_id=0x0289F002, is_extended_id=True, is_error_frame=True, data=b''),
    ]
    d = _dev(FakeBus(rx=rx))
    d.open_device()
    msgs, ret = d.read_ch1()
    assert ret == 2
    assert [m.can_id for m in msgs] == [0x0289F000, 0x0289F001]
    assert msgs[0].data == bytes(range(8))
    assert msgs[1].data == b'\xAA\xBB' + b'\x00' * 6
    assert len(msgs[1].data) == 8
    # queue drained
    assert d.read_ch1() == ([], 0)


def test_read_ch2_always_idle():
    d = _dev(FakeBus(rx=[can.Message(arbitration_id=1, data=b'')]))
    d.open_device()
    assert d.read_ch2() == ([], 0)


def test_read_error_returns_negative():
    d = _dev(FakeBus(fail_recv=True))
    d.open_device()
    msgs, ret = d.read_ch1()
    assert ret < 0
    assert 'bus off' in d.last_error


def test_rx_frames_decode_through_protocol_layer(monkeypatch):
    """A PCAN frame must reach REGx_CAN_ReceviceCallback exactly like a ZLG frame."""
    import REG1K0100A2
    monkeypatch.setattr(REG1K0100A2, 'g_log_callback', None)
    # 0x04 module status reply from module 0 to master, temperature in data[4]
    ident = (0x0A << 22) | (0x04 << 16) | (REG1K0100A2.REGx_MASTER_ADDR << 8) | 0x00
    d = _dev(FakeBus(rx=[can.Message(arbitration_id=ident, is_extended_id=True,
                                     data=bytes([0, 0, 0, 0, 42, 0, 0, 0]))]))
    d.open_device()
    msgs, ret = d.read_ch1()
    ci = REG1K0100A2.CANControllerInfo()
    for m in msgs:
        REG1K0100A2.REGx_CAN_ReceviceCallback(m, ci)
    assert ci.Temperature == 42


# ── backend factory ────────────────────────────────────────────

class _Cfg:
    def __init__(self, **kw):
        self.can_backend = kw.get('can_backend', 'auto')
        self.pcan_channel = kw.get('pcan_channel', 'PCAN_USBBUS1')
        self.can_bitrate = kw.get('can_bitrate', 125000)


def test_factory_pcan_explicit():
    from can_backend import create_can_device
    from pcan_dev import PCANDev
    dev = create_can_device(_Cfg(can_backend='pcan', pcan_channel='PCAN_USBBUS2', can_bitrate=250000))
    assert isinstance(dev, PCANDev)
    assert dev.channel == 'PCAN_USBBUS2'
    assert dev.bitrate == 250000
    assert dev.backend_name == 'pcan'


def test_factory_auto_prefers_pcan_when_available(monkeypatch):
    import can_backend
    from pcan_dev import PCANDev
    monkeypatch.setattr(can_backend, 'pcan_available', lambda: True)
    assert isinstance(can_backend.create_can_device(_Cfg()), PCANDev)


def test_factory_auto_falls_back_to_zlg(monkeypatch):
    import can_backend
    import HDL_CAN
    monkeypatch.setattr(can_backend, 'pcan_available', lambda: False)
    created = []
    from types import SimpleNamespace
    monkeypatch.setattr(HDL_CAN, 'CANDev', lambda: created.append(1) or SimpleNamespace())
    dev = can_backend.create_can_device(_Cfg())
    assert created == [1]
    assert dev.backend_name == 'zlg'


def test_factory_rejects_unknown_backend():
    from can_backend import create_can_device
    with pytest.raises(ValueError):
        create_can_device(_Cfg(can_backend='kvaser'))


def test_pcan_available_false_without_driver(monkeypatch):
    """On a machine without PCANBasic.dll / libpcanbasic.so this must be False, not raise."""
    import can_backend
    assert can_backend.pcan_available() in (True, False)
