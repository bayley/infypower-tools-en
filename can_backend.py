"""
Picks the CAN adapter backend from config.json:

    "can_backend": "auto" | "zlg" | "pcan"

  zlg   -> HDL_CAN.CANDev   (ZLG USBCAN-2A / USBCAN-II via ControlCAN.dll)
  pcan  -> pcan_dev.PCANDev (PEAK PCAN-USB & friends via python-can / PCAN-Basic)
  auto  -> pcan if python-can and PCANBasic.dll load and a PCAN channel is
           attached, otherwise zlg.
"""


def pcan_available() -> bool:
    """True when python-can + PCANBasic.dll load and at least one PCAN channel is attached."""
    try:
        from can.interfaces.pcan.basic import (PCANBasic, PCAN_NONEBUS,
                                               PCAN_ATTACHED_CHANNELS_COUNT,
                                               PCAN_ERROR_OK)
    except Exception:
        return False
    try:
        api = PCANBasic()   # loads the DLL; raises OSError when missing
    except Exception:
        return False
    try:
        res, count = api.GetValue(PCAN_NONEBUS, PCAN_ATTACHED_CHANNELS_COUNT)
        if res == PCAN_ERROR_OK:
            return int(count) > 0
    except Exception:
        pass
    return True   # DLL loads but old API can't enumerate: assume the adapter is there


def create_can_device(config):
    backend = (getattr(config, 'can_backend', 'auto') or 'auto').lower()
    if backend == 'auto':
        backend = 'pcan' if pcan_available() else 'zlg'
    if backend == 'pcan':
        from pcan_dev import PCANDev
        dev = PCANDev(channel=getattr(config, 'pcan_channel', 'PCAN_USBBUS1'),
                      bitrate=getattr(config, 'can_bitrate', 125000))
    elif backend == 'zlg':
        from HDL_CAN import CANDev
        dev = CANDev()
    else:
        raise ValueError(f'Unknown can_backend {backend!r}; use "auto", "zlg" or "pcan"')
    dev.backend_name = backend
    print(f'CAN backend: {backend}')
    return dev
