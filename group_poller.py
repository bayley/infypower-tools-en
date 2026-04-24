import time
from REG1K0100A2 import (
    REGx_GroupReadVoltCurr,
    REGx_ReadOutputRequest,         # 0x09
    REGx_ReadStateRequest,          # 0x04
    REGx_GroupReadModulesStatus,    # 0x04 + 0x0B
    REGx_RegisterListener,
    REGx_UnregisterListener,
    REGx_DEVICE_CODE,
)
from group_state import ModuleState


class GroupPoller:
    def __init__(self, state, schedule_fn, poll_interval_ms: int = 100):
        self._state = state
        self._sched = schedule_fn
        self._interval = poll_interval_ms
        self._running = False
        # step 0: 组 0x08；step 2k-1 (k=1..N): 0x09 mod[k-1]；step 2k: 0x04 mod[k-1]；N=0 时永远停在 0
        self._step_idx = 0
        # T9 discover_modules / T10 attach 会用到的预初始化字段
        self._discover_seen = set()
        self._attached = False

    def start_cycle(self):
        self._running = True
        self._step_idx = 0
        self._do_current_step()

    def stop(self):
        self._running = False

    def _module_addrs(self):
        return sorted(self._state.modules.keys())

    def _do_current_step(self):
        if not self._running:
            return
        addrs = self._module_addrs()
        N = len(addrs)
        i = self._step_idx
        total = 1 + 2 * N
        if i == 0:
            REGx_GroupReadVoltCurr(self._state.group_id)
        else:
            # Steps 1..2N: interleaved per module (0x09 then 0x04 for each module)
            # step 1 = 0x09 addr[0], step 2 = 0x04 addr[0]
            # step 3 = 0x09 addr[1], step 4 = 0x04 addr[1]  etc.
            module_idx = (i - 1) // 2
            if module_idx >= N:
                # 模块在周期中途被踢出（T10 跨组检测）→ 跳过此步
                pass
            else:
                is_state = (i - 1) % 2 == 1
                addr = addrs[module_idx]
                if is_state:
                    REGx_ReadStateRequest(addr)
                else:
                    REGx_ReadOutputRequest(addr)
        # 准备下一步
        self._step_idx = (i + 1) % total if N > 0 else 0
        self._sched(self._interval, self._next_step_wrapper)

    def _next_step_wrapper(self):
        if self._running:
            self._do_current_step()

    def attach(self):
        if not self._attached:
            REGx_RegisterListener(self._on_rx)
            self._attached = True

    def detach(self):
        if self._attached:
            REGx_UnregisterListener(self._on_rx)
            self._attached = False

    def discover_modules(self, group_id: int, timeout_ms: int, on_finish):
        """启动一次组级模块发现：发 0x04 广播，timeout_ms 后通过 on_finish 回调返回所发现的模块地址集合。
        注意：调用方应当在 on_finish 内决定是否启动 start_cycle()，不要并发调用。
        """
        self._state.group_id = group_id
        _seen = set()
        self._discover_seen = _seen   # _on_rx 写入此局部别名（同时也是实例字段）
        self.attach()
        REGx_GroupReadModulesStatus(group_id)

        def _finish():
            for addr in _seen:
                if addr not in self._state.modules:
                    self._state.modules[addr] = ModuleState(addr=addr, last_seen=time.time())
            on_finish(set(_seen))   # 传副本，避免后续 RX 突变调用方持有的引用

        self._sched(timeout_ms, _finish)

    def _on_rx(self, ev):
        # T9 scope: only handles group-level 0x04 discovery replies
        # T10 will extend this to handle 0x09 / 0x04 / 0x08 for ongoing data updates
        if ev.cmdCode == 0x04 and ev.deviceCode == 0x0B and ev.srcAddr != 0xF0:
            self._discover_seen.add(ev.srcAddr)
