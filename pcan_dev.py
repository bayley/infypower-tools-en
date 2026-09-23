"""
PEAK PCAN backend (PCAN-USB, PCAN-USB FD, PCAN-PCI, ...) built on python-can.

Exposes the same interface as HDL_CAN.CANDev (the ZLG USBCAN backend) so the
rest of the app does not care which adapter is plugged in:

    open_device() -> bool
    close_device()
    isCanOpen
    send_data_ch1(can_id, data) / send_data_ch2(can_id, data)
    read_ch1() / read_ch2() -> (list[CANMsg], ret)   ret < 0 means bus error

Requirements on Windows:
  * PEAK device driver package, installed with the "PCAN-Basic API" option
    (this provides PCANBasic.dll). https://www.peak-system.com/quick/DrvSetup
  * pip install python-can

A PCAN-USB adapter has a single channel, so it is mapped to CAN1. CAN2 is
reported as idle. Use pcan_channel in config.json to pick the adapter
(PCAN_USBBUS1, PCAN_USBBUS2, ...).
"""
from typing import Any, Callable, List, Optional, Tuple

from HDL_CAN import CANMsg

_RX_BATCH_MAX = 2500   # matches the ZLG backend's receive buffer


class PCANDev:
    def __init__(self, channel: str = 'PCAN_USBBUS1', bitrate: int = 125000,
                 bus_factory: Optional[Callable[..., Any]] = None):
        self.channel = channel
        self.bitrate = int(bitrate)
        self.isCanOpen = False
        self.last_error = ''
        self._bus = None
        # Injectable for tests; defaults to can.Bus(...)
        self._bus_factory = bus_factory

    # ── lifecycle ────────────────────────────────────────────────
    def open_device(self) -> bool:
        if self.isCanOpen:
            return True
        try:
            import can
        except ImportError:
            self.last_error = 'python-can is not installed (pip install python-can)'
            print(f'PCAN open failed: {self.last_error}')
            return False

        factory = self._bus_factory or (
            lambda: can.Bus(interface='pcan', channel=self.channel,
                            bitrate=self.bitrate))
        try:
            self._bus = factory()
        except Exception as e:   # can.CanInitializationError, OSError (missing DLL), ...
            self.last_error = f'{type(e).__name__}: {e}'
            self._bus = None
            print(f'PCAN open failed on {self.channel}: {self.last_error}')
            return False

        self.isCanOpen = True
        self.last_error = ''
        print(f'PCAN opened {self.channel} @ {self.bitrate} bps')
        return True

    def close_device(self):
        bus, self._bus = self._bus, None
        self.isCanOpen = False
        if bus is not None:
            try:
                bus.shutdown()
            except Exception:
                pass

    # ── TX ───────────────────────────────────────────────────────
    def send_data(self, channel: int, can_id: int, data: bytes):
        if not self.isCanOpen or self._bus is None:
            return
        if channel != 0:
            # Single-channel adapter: only CAN1 exists.
            return
        import can
        can_id = can_id & 0x1FFFFFFF
        msg = can.Message(arbitration_id=can_id,
                          is_extended_id=can_id > 0x7FF,
                          data=bytes(data)[:8])
        try:
            self._bus.send(msg)
        except Exception as e:
            self.last_error = f'{type(e).__name__}: {e}'
            print(f'CAN{channel + 1} channel send failed: {self.last_error}')

    def send_data_ch1(self, can_id: int, data: bytes):
        self.send_data(0, can_id, data)

    def send_data_ch2(self, can_id: int, data: bytes):
        self.send_data(1, can_id, data)

    # ── RX ───────────────────────────────────────────────────────
    def read_ch(self, channel: int) -> Tuple[List[CANMsg], Any]:
        if not self.isCanOpen or self._bus is None or channel != 0:
            return [], 0
        out: List[CANMsg] = []
        try:
            for _ in range(_RX_BATCH_MAX):
                m = self._bus.recv(timeout=0)
                if m is None:
                    break
                if getattr(m, 'is_error_frame', False) or getattr(m, 'is_remote_frame', False):
                    continue
                cm = CANMsg()
                cm.can_id = int(m.arbitration_id)
                # The ZLG backend always yields exactly 8 data bytes; keep that contract.
                cm.data = bytes(m.data[:8]).ljust(8, b'\x00')
                out.append(cm)
        except Exception as e:
            self.last_error = f'{type(e).__name__}: {e}'
            print(f'PCAN receive failed: {self.last_error}')
            return out, -1
        return out, len(out)

    def read_ch1(self):
        return self.read_ch(0)

    def read_ch2(self):
        return self.read_ch(1)
