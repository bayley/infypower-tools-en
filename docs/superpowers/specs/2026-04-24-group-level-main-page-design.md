# 主页面组级控制改造 设计规范

- **日期**：2026-04-24
- **分支**：`feat/group-control-main`
- **背景**：当前主页面只能控制单个模块（硬编码地址 `0x00`，设备号 `0x0A`）。需要改造为**组级控制**：一次操作一个组（设备号 `0x0B`，目的地址 = 组号），允许在多个组之间切换。系统级（广播给所有组）超出本次范围。
- **协议参考**：`doc/充电模块CAN通讯协议V1.09 20240510.md`

## 1. 心智模型

> **软件 = 一个组的远程控制台。任何时刻只对一个组发心跳和命令，组之外的世界软件不感知。**

理由：协议 §3.1 规定模块 10s 内未收到任何命令会触发通讯中断保护并自动关机；这意味着软件必须周期性向"当前关注的对象"发心跳。同时只能维持一个对象的心跳，自然推出"一次只管一个组"。

## 2. 用户操作主线

1. 启动 → 主页加载，所有控件 disabled，组选择器填入 `config.default_group`（默认 1）
2. 用户点 **打开 CAN** → CAN 收发器就绪，组选择器解锁
3. 用户在组选择器选一个组 → **绑定动作**：
   - 立即向该组发一次广播探测 `0x04`（设备号 `0x0B`，目的地址 = 组号）
   - 等 600ms 收集回复，每条 srcAddr 是一个组内模块 → 模块表初始化
   - 启动周期心跳调度（§4）
   - 组控制控件解锁
4. 运行期：调电压 / 总电流并设定下发；启停组输出；模块表里点 💤（休眠）/ 💡（绿灯闪）
5. 切组 → **解绑旧组**（停止旧组心跳，**不主动下发任何命令**）→ **绑定新组**（重复 3）

### 2.1 切组的副作用提示

切组那一刻起，旧组在约 10s 后会因协议通讯中断保护自动关机。这是协议设计而非缺陷。

→ 切组时，若旧组当前为"开机"状态，**弹一个非阻塞 InfoBar**：

> ⚠ 已切到组 X。旧组（组 Y）将在约 10s 后因协议通讯中断保护自动关机。

旧组若已关机则不提示。

### 2.2 三个特殊状态

| 状态 | 表现 |
|---|---|
| CAN 未打开 | 组选择器 + 所有控件 + 模块表禁用，曲线区显示"等待 CAN 打开"占位 |
| CAN 已打开但组探不到模块 | 组选择器可用、控制控件禁用、模块表显示空状态卡 *"未发现组 X 内的模块（请检查组号 / 模块拨码 / CAN 接线）"* |
| CAN 已打开 + 至少一个模块在线 | 完整功能 |

## 3. 整体布局（左信息流 + 右控制栏）

```
┌──────────────────────────────────────────────────────────┐
│ [⏻ 打开 CAN]  操作组：[组 1 ▾] [🔄]    CAN1●  CAN2●     │  ← 顶部条
├──────────────────────────────────────┬───────────────────┤
│ 组聚合（4 个数字大字）                │  组控制            │
│ ┌─────────┬─────────┬────────┬──────┐ │  设定电压(V)       │
│ │ 组电压  │ 组总电流│ 组功率 │ 模块│  │  [ 512.0     ]    │
│ └─────────┴─────────┴────────┴──────┘ │                   │
│                                        │  设定组总电流(A)   │
│ 实时曲线               显示：[整组 ▾] │  [ 40.0      ]    │
│ ┌──────────────────────────────────┐  │  [  设定下发  ]    │
│ │  ╱╲                              │  │  ─────────         │
│ │ ╱  ╲___                          │  │  组开关机          │
│ │              ╱                   │  │  [⏻ 启动组输出]    │
│ │             ╱                    │  │  [⏹ 关闭组输出]    │
│ └──────────────────────────────────┘  │                   │
│                                        │  组当前：⚪ 已开机 │
│ 组内模块                                │                   │
│ ┌──────┬───────┬──────┬────┬──┬──┐    │                   │
│ │ 地址 │ 电压  │电流  │ ℃  │💤│💡│    │                   │
│ │ 0x00 │512.5V │12.7A │ 34 │[]│[]│    │                   │
│ │ 0x01 │512.4V │12.8A │ 35 │[✓]│[]│   │                   │
│ │ 0x02 │ — —  │ — — │ —  │[]│[]│ ⚠   │                   │
│ └──────┴───────┴──────┴────┴──┴──┘    │                   │
└──────────────────────────────────────┴───────────────────┘
```

- 顶部条：CAN 开关 + 组选择器 + 手动刷新按钮 🔄 + CAN1/CAN2 状态徽章
- 左侧（约 70%）：自上而下 = 组聚合卡 → 实时曲线 → 模块表
- 右侧（约 30%）：组控制栏

## 4. 心跳轮询调度

### 4.1 一个完整周期发送的命令

| 序号 | 命令 | 设备号 / 目的地址 | 拿到的数据 |
|---|---|---|---|
| ① | `0x08` | `0x0B` + 当前组号 | 组聚合 V + 组总 I（定点格式） |
| ② × N | `0x09` | `0x0A` + 模块地址 | 该模块 V/I |
| ③ × N | `0x04` | `0x0A` + 模块地址 | 模块状态 + 温度 + 组号验证 |

> 选 `0x08` 而不是 `0x01`：定点格式更稳，不易在 CAN 抖动时变 NaN。
> N = 当前已知模块数。

### 4.2 节奏

- 命令间隔：**100ms**（协议建议 50~200ms，取 100ms 留余量给 RX 处理）
- 周期总长：`(1 + 2N) × 100ms`
  - 3 模块 → 700ms ≈ 1.4 Hz
  - 6 模块 → 1300ms ≈ 0.77 Hz
  - 10 模块 → 2100ms ≈ 0.48 Hz
- 实现：`QTimer.singleShot(100, send_next)` 链式调度，避免周期 timer 抖动

### 4.3 RX 即 push

每条回复抵达即更新对应数据 + push 一个图表点，不等周期结束。"曲线更新速度 = 轮询速度"自然成立。

## 5. 模块发现 / 离线判定

### 5.1 初始发现

切组那一刻，发一次组级广播 `0x04`（设备号 `0x0B`，目的地址 = 组号）。协议保证 *"该组所有模块以模块地址号回复"*（即每条回复 `srcAddr` = 组内一个模块的地址）。等 `group_discover_timeout_ms`（默认 600ms）收集 srcAddr → 初始模块列表。若超时仍无回复 → 显示"未发现组 X 内的模块"提示。

### 5.2 周期验证

每周期对每个已知模块发模块级 `0x04`，回复 `data[2]` 即模块当前组号；若 ≠ 当前组号 → 该模块被踢出本组（移出模块表）。

每个模块维护 `last_seen` 时间戳。

### 5.3 离线判定四态

阈值都来自 `config.json`，下表给出默认值。

| 状态 | 触发条件（`now - last_seen` 与默认阈值） | 视觉 |
|---|---|---|
| online  | < `module_pending_timeout_ms` (默认 3000) | 正常显示 |
| pending | ≥ pending 阈值且 < `module_offline_timeout_ms` (默认 10000) | V/I 灰色 `— —`，温度 `—`，行半透明 |
| offline | ≥ offline 阈值且 < `module_gone_timeout_ms` (默认 30000) | 行变红 + InfoBadge 警告，**不删除** |
| gone    | ≥ `module_gone_timeout_ms` (默认 30000) | 自动从模块表移除 |

### 5.4 手动刷新

组选择器旁的 🔄 按钮 = 重新跑一次"初始发现"。

## 6. 实时曲线

### 6.1 结构变化

`RealtimeChart` 从"外部 timer 驱动 push"改为"RX 回调驱动 push + target 切换"。

- 增加 **target**：`'group'` 或 `module_addr (int)`
- 增加 **target dropdown**：放在 chart widget 顶部右侧，紧挨现有暂停按钮，选项动态从模块表生成：`整组 / 模块 0x00 / 模块 0x01 / ...`

### 6.2 API

| 方法 | 触发 |
|---|---|
| `set_target(target)` | dropdown 变化时；**清空缓冲区**重新开始 |
| `push_group(V, I, V*I)` | 组级 `0x08` RX 回调 |
| `push_module(addr, V, I)` | 模块级 `0x09` RX 回调；仅当 `addr == current_target` 时进入缓冲区 |

### 6.3 Y 轴自适应

- target = 'group'：左 Y 轴 V 量程 = `config.voltage_max`；右 Y 轴功率量程 = `voltage_max × current_max × N`（N 动态）
- target = module：量程退化为单模块 `voltage_max × current_max`
- 三色 V/I/P 不变

### 6.4 暂停按钮

现有暂停语义不变。target 切换时清空缓冲区 + 自动恢复运行（不沿用上一个 target 的暂停态）。

### 6.5 main.py 对接变化

- 删除 `updateTableWiget` 里的 `realtimeChart.push(...)`
- RX 回调里识别命令号（注意回复方向：dst=主控地址 0xF0，src 由设备号决定）：
  - `cmdCode==0x08` + `deviceCode==0x0B` + `srcAddr==当前组号` → `chart.push_group(V, I, V*I)`
    - 协议 §2.2：*"当命令号为 0x01 或 0x02，设备号为 0x0B 时，模块回复信息的源地址为模块组号"*；0x08 是 0x01 的定点版本，按相同规则
  - `cmdCode==0x09` + `deviceCode==0x0A` + `srcAddr==某模块地址` → `chart.push_module(srcAddr, V, I)`

## 7. 组控制面板

### 7.1 控件

| 控件 | 命令 | 弹确认 |
|---|---|---|
| 设定下发 | `0x1B`（组级 V + 组总 I） | ❌ 不弹（节奏要快） |
| ⏻ 启动组输出 | `0x1A`（组级，data[0]=0x00） | ✅ 弹 MessageBox |
| ⏹ 关闭组输出 | `0x1A`（组级，data[0]=0x01） | ✅ 弹 MessageBox |

### 7.2 输入范围

- 电压：`config.voltage_min ~ voltage_max`
- 组总电流：`0 ~ current_max × len(modules)` （动态上限，模块数变化跟着变）

### 7.3 组当前状态

派生：组电压 > 5V 视为开机（沿用现有逻辑）；同时也可以从任一模块的 `0x04` 状态表 0 bit3 获取，两者矛盾时取后者（更权威）。

## 8. 单模块操作（模块表每行）

### 8.1 操作集

只保留两个安全操作（详见 §13 协议冲突分析）：

| 列 | 命令 | 类型 | 弹确认 |
|---|---|---|---|
| 💤 休眠 | `0x19` 模块级 | CheckBox（双向，从 `0x04` 状态表 0 bit4 读回） | ❌ |
| 💡 绿灯闪烁 | `0x14` 模块级 | CheckBox（本地 toggle，协议无读回） | ❌ |

### 8.2 行级告警

状态表 0~3 中告警 / 故障位置位时，地址列旁加红色 `IconInfoBadge`。鼠标 hover 显示 tooltip 列出告警字符串：

- "通讯中断告警" (status0 bit7)
- "风道不畅" (status0 bit6)
- "模块放电异常" (status0 bit5)
- "模块休眠" (status0 bit4)
- "模块故障告警" (status1 bit1)
- "过温告警" (status1 bit4)
- ... 依协议状态表 0~3 完整解码

### 8.3 离线行

`pending` / `offline` 状态行的 💤 / 💡 列禁用。

## 9. 数据模型（新建 `group_state.py`）

```python
@dataclass
class ModuleState:
    addr: int
    voltage: float = 0.0           # 来自 0x09
    current: float = 0.0           # 来自 0x09
    temperature: int = 0           # 0x04 data[4]，有符号 8bit
    status0: int = 0               # 0x04 data[7]
    status1: int = 0               # 0x04 data[6]
    status2: int = 0               # 0x04 data[5]
    status3: int = 0               # 0x04 data[3]
    group_id_reported: int = 0     # 0x04 data[2]
    sleeping: bool = False         # 派生自 status0 bit4
    led_blinking: bool = False     # 本地 toggle
    last_seen: float = 0.0         # time.time()

    @property
    def lifecycle(self) -> str: ...        # 'online' | 'pending' | 'offline' | 'gone'

    @property
    def alarms(self) -> list[str]: ...     # 解码状态位 → 中文字符串列表


@dataclass
class GroupState:
    group_id: int
    voltage: float = 0.0           # 0x08 组电压
    total_current: float = 0.0     # 0x08 组总电流
    modules: dict[int, ModuleState] = field(default_factory=dict)

    @property
    def total_power(self) -> float:
        return self.voltage * self.total_current

    @property
    def is_on(self) -> bool: ...   # 派生
```

旧 `CANControllerInfo` **保留供 `manual_widget` 继续使用**，不动。

## 10. CAN 协议层重构（`REG1K0100A2.py`）

### 10.1 现有发送函数加可选 `device_code` 参数

所有 `REGx_*` 发送函数当前硬编码 `deviceCode = REGx_DEVICE_CODE.SINGLE`。改为可选参数：

```python
def REGx_SetOutput(dstAddr, volt, curr, device_code=REGx_DEVICE_CODE.SINGLE):
    ...
def REGx_Launch(dstAddr, device_code=REGx_DEVICE_CODE.SINGLE):
    ...
# 等等
```

向后兼容：所有现有调用点（`manual_widget`、`main.py` 旧路径）默认 `SINGLE`，行为不变。

### 10.2 新增组级便捷包装

```python
def REGx_GroupSetOutput(group_id, volt, total_curr):     # 0x1B + 0x0B
    return REGx_SetSystemOutput(group_id, volt, total_curr,
                                device_code=REGx_DEVICE_CODE.GROUP)

def REGx_GroupLaunch(group_id):                          # 0x1A + 0x0B + data[0]=0
def REGx_GroupClose(group_id):                           # 0x1A + 0x0B + data[0]=1
def REGx_GroupReadVoltCurr(group_id):                    # 0x08 + 0x0B
def REGx_GroupReadModulesStatus(group_id):               # 0x04 + 0x0B（广播给组内每个模块）
```

### 10.3 RX 回调重构

`REGx_CAN_ReceviceCallback` 现在直接修改全局 `canController_info`。改为：

1. 解析 frame → 返回结构化 `RxEvent(deviceCode, cmdCode, srcAddr, dstAddr, data)`
2. 注册多个 listener：
   - 旧 listener：填 `CANControllerInfo`（`manual_widget` 用）
   - 新 listener：填 `GroupState` + 通知 chart push

旧 / 新路径完全独立，迁移期可同时跑。

### 10.4 `GroupPoller` 类（新建 `group_poller.py`）

负责 §4 的链式调度。依赖 `GroupState` 实例与 CAN 设备。生命周期由 `MainWindow` 控制：`start(group_id)`、`stop()`、`switch_group(new_id)`。

旧的 `REGx_Poll` 改名为 `REGx_PollLegacy`（手动操作页继续用）。

## 11. 配置（`config.json` / `AppConfig`）

新增字段：

```json
{
  "device_name": "REG1K0100A2 充电模块",
  "voltage_max": 1000.0,
  "voltage_min": 150.0,
  "current_max": 100.0,
  "current_min": 0.0,
  "default_group": 1,
  "group_range_max": 15,
  "module_pending_timeout_ms": 3000,
  "module_offline_timeout_ms": 10000,
  "module_gone_timeout_ms": 30000,
  "poll_interval_ms": 100,
  "group_discover_timeout_ms": 600
}
```

`ConfigManager.load()` 用 `data.get(..., default)` 读取，向后兼容旧 `config.json`（缺字段时 fallback 到默认）。

## 12. 错误处理

| 场景 | 行为 |
|---|---|
| CAN 关闭 | 组选择器禁用、所有控件禁用、模块表清空、`GroupPoller.stop()` |
| CAN 打开但组探不到模块 | 模块表显示空状态卡；组控制控件禁用；图表显示等待 |
| CAN 数据错误 (errorCode != 0) | CAN 日志红色高亮，但不打断主页节奏 |
| 模块状态告警位置位 | 行级 InfoBadge + hover tooltip |

## 13. 协议冲突分析（决定单模块操作集时的依据）

| 命令 | 单模块操作在"组用法"下是否安全？ | 原因 |
|---|---|---|
| `0x19` 休眠 | ✅ 推荐 | 协议 §3.5 给出的官方"踢出组均流"用法 |
| `0x14` 绿灯闪烁 | ✅ 安全 | 纯指示灯，不影响电流输出 |
| `0x1A` 单模块开关机 | ❌ 不暴露 | 破坏 `0x1B` 已分配的均流，输出会塌陷或超配 |
| `0x1C` 单模块 V/I | ❌ 不暴露 | 协议 §3.3 明确 `0x1B`/`0x1C` 互斥 |
| `0x13` 单模块 Walk-In | ❌ 不暴露 | 组软起曲线错位 |
| `0x16` 设置模块组号 | ❌ 不暴露 | 直接改模块归属，视图瞬间崩；属配置类 |
| `0x1F` 地址分配方式 | ❌ 不暴露 | 系统级拓扑配置 |
| `0x0F` 全部 sub-cmd | ❌ 不暴露 | 配置类 / 广播类（工作模式 / 噪音 / 高低压 / 液冷温度），单模块差异化破坏组语义 |

**主页 = 运行时控制；手动操作页 = 配置 + 诊断 + 低级**。一切"破坏组语义"的命令保留在手动操作页，操作时心理提示自带。

## 14. 测试策略

新增（沿用 `pytest` + `tests/` 目录）：

- **`tests/test_group_state.py`**
  - `ModuleState.lifecycle` 状态机（4 态）
  - `ModuleState.alarms` 状态位解码（覆盖协议状态表 0~3 全部已定义位）
  - `GroupState.is_on` 派生
- **`tests/test_reg1k_group_helpers.py`**
  - mock `g_candevice`，断言 `REGx_GroupSetOutput(2, 512.0, 40.0)` 发出的 Identifier = `0x02DB02F0`、data 编码正确
  - 验证组级 `0x1A` / `0x04` / `0x08` Identifier 编码
- **`tests/test_group_poller.py`**
  - mock CAN 设备，注入响应序列
  - 验证调度顺序、模块发现、离线检测状态机
- **`tests/test_config_manager.py`** 扩展
  - 旧 `config.json` 缺新字段时 fallback 到默认

UI 层（`main.py` / `chart_widget.py` / 新组件）**不写自动化测试**，靠手动跑 + `build_nuitka_debug.bat` 调试包。

## 15. 实施分支

- 分支名：`feat/group-control-main`（已创建）
- 开发期间手动操作页 + CAN 协议底层 `CANControllerInfo` 路径不打断
- 新组级路径独立可关，便于灰度对比验证

## 16. 不在本次范围

- 系统级（设备号 `0x0A` + 广播 `0x3F`）控制
- 组的拓扑编辑（创建组 / 删除组 / 改模块归属）
- 多组并列显示
- 组级 Walk-In / 组级工作模式 / 组级液冷温度 等组级配置命令的 UI（这些可以放到手动操作页或后续迭代）
