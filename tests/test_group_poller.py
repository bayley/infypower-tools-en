import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class _StepScheduler:
    """手工 step 的假调度器，记录所有调用"""
    def __init__(self):
        self.queue = []  # list of (delay_ms, callback)
    def __call__(self, delay_ms, cb):
        self.queue.append((delay_ms, cb))
    def step(self):
        if not self.queue:
            return False
        _, cb = self.queue.pop(0)
        cb()
        return True


@pytest.fixture
def setup(mock_can):
    from group_state import GroupState, ModuleState
    state = GroupState(group_id=1)
    state.modules[0x00] = ModuleState(addr=0x00, last_seen=0.0)
    state.modules[0x01] = ModuleState(addr=0x01, last_seen=0.0)
    sch = _StepScheduler()
    return mock_can, state, sch


def test_poller_sends_group_then_per_module_x9_x4(setup):
    from group_poller import GroupPoller
    can, state, sch = setup
    poller = GroupPoller(state=state, schedule_fn=sch, poll_interval_ms=100)
    poller.start_cycle()

    # 立即发了组 0x08
    assert can.sent[0][0] == 0x02C801F0  # cmd=0x08 device=0x0B dst=0x01

    sch.step()
    assert can.sent[1][0] == 0x028900F0  # cmd=0x09 device=0x0A dst=0x00

    sch.step()
    assert can.sent[2][0] == 0x028400F0  # cmd=0x04 device=0x0A dst=0x00

    sch.step()
    assert can.sent[3][0] == 0x028901F0

    sch.step()
    assert can.sent[4][0] == 0x028401F0


def test_poller_loops_back_after_full_cycle(setup):
    from group_poller import GroupPoller
    can, state, sch = setup
    poller = GroupPoller(state=state, schedule_fn=sch, poll_interval_ms=100)
    poller.start_cycle()
    while sch.step():
        if len(can.sent) >= 5:
            break

    sch.step()
    assert can.sent[5][0] == 0x02C801F0


def test_poller_stop_cancels_chain(setup):
    from group_poller import GroupPoller
    can, state, sch = setup
    poller = GroupPoller(state=state, schedule_fn=sch, poll_interval_ms=100)
    poller.start_cycle()
    poller.stop()
    sch.step()
    assert len(can.sent) == 1  # 只有起步那一条


def test_discover_collects_srcAddrs_into_state_modules(setup, monkeypatch):
    import REG1K0100A2
    from group_poller import GroupPoller
    can, state, sch = setup
    state.modules.clear()  # 重置，模拟刚切组
    poller = GroupPoller(state=state, schedule_fn=sch, poll_interval_ms=100)

    captured_finish = []
    poller.discover_modules(group_id=1, timeout_ms=600,
                             on_finish=lambda found: captured_finish.append(found))

    # 验证发了组级 0x04
    assert can.sent[-1][0] == 0x02C401F0

    # 模拟 3 个模块回复（组级 0x04 回复，srcAddr = 模块地址）
    for mod_addr in (0x00, 0x01, 0x02):
        msg = REG1K0100A2.RxEvent(errorCode=0, deviceCode=0x0B, cmdCode=0x04,
                                   dstAddr=0xF0, srcAddr=mod_addr,
                                   data=bytes([0, 0, 1, 0, 25, 0, 0, 0]))
        # 直接喂给 poller 的 listener
        poller._on_rx(msg)

    # 模拟 timeout 触发
    sch.step()  # discover 的超时回调

    assert sorted(state.modules.keys()) == [0x00, 0x01, 0x02]
    assert captured_finish == [{0x00, 0x01, 0x02}]


def test_discover_calls_on_finish_with_empty_set_on_timeout(setup):
    from group_poller import GroupPoller
    can, state, sch = setup
    state.modules.clear()
    poller = GroupPoller(state=state, schedule_fn=sch, poll_interval_ms=100)
    captured = []
    poller.discover_modules(group_id=2, timeout_ms=600,
                             on_finish=lambda found: captured.append(found))
    sch.step()
    assert captured == [set()]
