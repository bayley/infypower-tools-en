import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class MockCAN:
    """Captures CAN frames sent via send_data_ch1 for assertion in tests."""

    def __init__(self):
        self.sent = []  # list of (can_id, bytes)

    def send_data_ch1(self, can_id, data):
        self.sent.append((can_id, bytes(data)))
        return 1


@pytest.fixture
def mock_can(monkeypatch):
    import REG1K0100A2
    mc = MockCAN()
    REG1K0100A2.REGx_Init(mc)
    monkeypatch.setattr(REG1K0100A2, 'g_log_callback', None)
    return mc
