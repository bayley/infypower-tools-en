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

    @property
    def alarms(self) -> list[str]:
        out = []
        s0, s1, s2 = self.status0, self.status1, self.status2

        if s0 & (1 << 7): out.append("Communication loss alarm")
        if s0 & (1 << 6): out.append("Airflow blocked")
        if s0 & (1 << 5): out.append("Module discharge abnormal")
        if s0 & (1 << 3): out.append("Input or bus abnormal")

        # 注意：status1 bit 6（Walk-In 使能）是默认特性标志，不算告警
        if s1 & (1 << 7): out.append("Module communication loss alarm")
        if s1 & (1 << 5): out.append("Output overvoltage alarm")
        if s1 & (1 << 4): out.append("Overtemperature alarm")
        if s1 & (1 << 3): out.append("Fan fault alarm")
        if s1 & (1 << 2): out.append("Module protection alarm")
        if s1 & (1 << 1): out.append("Module fault alarm")

        if s2 & (1 << 7): out.append("Module PFC side is off")
        if s2 & (1 << 6): out.append("Input overvoltage alarm")
        if s2 & (1 << 5): out.append("Input undervoltage alarm")
        if s2 & (1 << 4): out.append("Three-phase input imbalance alarm")
        if s2 & (1 << 3): out.append("Three-phase input phase-loss alarm")
        if s2 & (1 << 2): out.append("Severe module current imbalance")
        if s2 & (1 << 1): out.append("Duplicate module ID")

        return out


@dataclass
class GroupState:
    group_id: int
    voltage: float = 0.0
    total_current: float = 0.0
    modules: dict[int, ModuleState] = field(default_factory=dict)

    @property
    def total_power(self) -> float:
        return self.voltage * self.total_current

    @property
    def is_on(self) -> bool:
        return self.voltage > 5.0

    @property
    def module_count(self) -> int:
        return len(self.modules)
