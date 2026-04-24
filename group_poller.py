from REG1K0100A2 import (
    REGx_GroupReadVoltCurr,
    REGx_ReadOutputRequest,         # 0x09
    REGx_ReadStateRequest,          # 0x04
    REGx_GroupReadModulesStatus,    # 0x04 + 0x0B
    REGx_DEVICE_CODE,
)


class GroupPoller:
    def __init__(self, state, schedule_fn, poll_interval_ms: int = 100):
        self._state = state
        self._sched = schedule_fn
        self._interval = poll_interval_ms
        self._running = False
        self._step_idx = 0   # 0=group, 1..N=module idx for 0x09, N+1..2N=module idx for 0x04

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
