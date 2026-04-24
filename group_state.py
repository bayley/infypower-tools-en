from dataclasses import dataclass, field


@dataclass
class ModuleState:
    addr: int
    voltage: float = 0.0
    current: float = 0.0
    temperature: int = 0
    status0: int = 0
    status1: int = 0
    status2: int = 0
    status3: int = 0
    group_id_reported: int = 0
    led_blinking: bool = False
    last_seen: float = 0.0

    def lifecycle(self, now: float, pending_ms: int,
                  offline_ms: int, gone_ms: int) -> str:
        elapsed_ms = (now - self.last_seen) * 1000.0
        if elapsed_ms < pending_ms:
            return 'online'
        if elapsed_ms < offline_ms:
            return 'pending'
        if elapsed_ms < gone_ms:
            return 'offline'
        return 'gone'

    @property
    def sleeping(self) -> bool:
        return bool(self.status0 & (1 << 4))
