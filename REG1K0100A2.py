import struct
import time
import HDL_CAN

REGx_INPUT_AC_VOLT_MAX = 530  # Unit: V
REGx_INPUT_AC_VOLT_MIN = 260  # Unit: V
REGx_INPUT_AC_CURR_MAX = 58  # Unit: A
REGx_INPUT_AC_CURR_MIN = 0  # Unit: A

REGx_OUTPUT_DC_VOLT_MAX = 1000  # Unit: V
REGx_OUTPUT_DC_VOLT_MIN = 150  # Unit: V # Actual the minimum voltage is 150V
REGx_OUTPUT_DC_CURR_MAX = 100  # Unit: A
REGx_OUTPUT_DC_CURR_MIN = 0  # Unit: A

REGx_OUTPUT_POWER_MAX = 30000  # Unit: W

REGx_AUTOSHUTDOWN_NO_CAN_CND_TIMEOUT = 10  # Unit: s

REGx_MASTER_ADDR = 0xF0  # 0xF0~0xF8
REGx_BROADCAST_ADDR = 0x3F


class CANControllerInfo:
    AC_AB_Volt = 0
    AC1Curr = 0
    AC1Power = 0
    AC_BC_Volt = 0
    AC_CA_Volt = 0
    AC2Curr = 0
    AC2Power = 0
    DC_Output_Volt = 0
    DC_Output_Curr = 0
    DC_Output_Power = 0
    ACTotalPower = 0

    ChargerState = 0
    ChargerVolt = 0
    ChargerCurr = 0
    MaxChargerCurr = 0
    MaxChargerVolt = 0
    MaxChargePower = 0

    Temperature = 0

    # 0x01 / 0x08 系统电压电流
    SystemVolt = 0.0
    SystemCurr = 0.0
    # 0x02 模块数量
    ModuleCount = 0
    # 0x03 模块电压电流（浮点）
    ModuleVoltFloat = 0.0
    ModuleCurrFloat = 0.0
    # 0x0A 模块参数
    ParamVoltMax = 0.0
    ParamVoltMin = 0.0
    ParamCurrMax = 0.0
    ParamPower = 0.0
    # 0x0B 条码
    Barcode = ""
    # 0x0C 外部电压/允许电流
    ExternalVolt = 0.0
    AllowedCurr = 0.0


g_candevice = None
g_log_callback = None  # 由 ManualWidget 注册，签名: (direction: str, identifier: int, data: bytes, desc: str)
def REGx_Init(can_device):
    global g_candevice
    g_candevice = can_device
    return 0

def REGx_OUTPUT_DC_VOLT_IS_VALID(volt):
    return REGx_OUTPUT_DC_VOLT_MIN <= volt <= REGx_OUTPUT_DC_VOLT_MAX


def REGx_OUTPUT_DC_CURR_IS_VALID(curr):
    return REGx_OUTPUT_DC_CURR_MIN <= curr <= REGx_OUTPUT_DC_CURR_MAX


def REGx_OUTPUT_POWER_IS_VALID(power):
    return 0 <= power <= REGx_OUTPUT_POWER_MAX


class REGx_ERROR_CODE:
    NORMAL = 0
    NONE = 1
    CMD_ABNORMAL = 2
    DATA_ABNORMAL = 3
    ADDR_INVALID = 4
    LAUNCHING = 7


class REGx_DEVICE_CODE:
    SINGLE = 0x0A
    GROUP = 0x0B


class REGx_Msg_t:
    def __init__(self):
        self.errorCode = REGx_ERROR_CODE.NORMAL
        self.deviceCode = REGx_DEVICE_CODE.SINGLE
        self.cmdCode = 0
        self.dstAddr = 0
        self.srcAddr = 0
        self.data = bytearray(8)

def REGx_MsgSend(msg):
    TxData = bytearray(8)
    Identifier = 0
    Identifier |= (msg.srcAddr & 0xFF)
    Identifier |= (msg.dstAddr & 0xFF) << 8
    Identifier |= (msg.cmdCode & 0x3F) << 16
    Identifier |= (msg.deviceCode & 0x0F) << 22
    Identifier |= (msg.errorCode & 0x07) << 26
    TxData[:] = msg.data[:]
    formatted_identifier = f"({Identifier >> 24:02X} {Identifier >> 16 & 0xFF:02X} {Identifier >> 8 & 0xFF:02X} {Identifier & 0xFF:02X})"
    print(f"==> Identifier: {formatted_identifier} TxData: {TxData}")
    if g_log_callback:
        g_log_callback('TX', Identifier, bytes(TxData), "")
    return g_candevice.send_data_ch1(Identifier, TxData)


def REGx_ReadStateRequest(dstAddr, device_code=REGx_DEVICE_CODE.SINGLE):
    request = REGx_Msg_t()

    request.errorCode = REGx_ERROR_CODE.NORMAL
    request.deviceCode = device_code
    request.cmdCode = 0x04
    request.dstAddr = dstAddr
    request.srcAddr = REGx_MASTER_ADDR

    request.data = bytearray(8)
    REGx_MsgSend(request)

    return 0


def REGx_ReadInputRequest(dstAddr, device_code=REGx_DEVICE_CODE.SINGLE):
    request = REGx_Msg_t()

    request.errorCode = REGx_ERROR_CODE.NORMAL
    request.deviceCode = device_code
    request.cmdCode = 0x06
    request.dstAddr = dstAddr
    request.srcAddr = REGx_MASTER_ADDR

    request.data = bytearray(8)
    REGx_MsgSend(request)

    return 0


def REGx_ReadOutputRequest(dstAddr, device_code=REGx_DEVICE_CODE.SINGLE):
    request = REGx_Msg_t()

    request.errorCode = REGx_ERROR_CODE.NORMAL
    request.deviceCode = device_code
    request.cmdCode = 0x09
    request.dstAddr = dstAddr
    request.srcAddr = REGx_MASTER_ADDR

    request.data = bytearray(8)
    REGx_MsgSend(request)

    return 0



# 注意：此函数与 REGx_ReadModuleParams 发送相同的 0x0A 命令（读取模块参数：最大电压/最小电压/最大电流/额定功率）
# 保留此函数名以保持向后兼容性
def REGx_ReadOutputSetRequest(dstAddr, device_code=REGx_DEVICE_CODE.SINGLE):
    request = REGx_Msg_t()

    request.errorCode = REGx_ERROR_CODE.NORMAL
    request.deviceCode = device_code
    request.cmdCode = 0x0A
    request.dstAddr = dstAddr
    request.srcAddr = REGx_MASTER_ADDR

    request.data = bytearray(8)
    REGx_MsgSend(request)

    return 0

def REGx_ReadSystemVoltCurrFloat(dstAddr, device_code=REGx_DEVICE_CODE.SINGLE):
    request = REGx_Msg_t()
    request.errorCode = REGx_ERROR_CODE.NORMAL
    request.deviceCode = device_code
    request.cmdCode = 0x01
    request.dstAddr = dstAddr
    request.srcAddr = REGx_MASTER_ADDR
    request.data = bytearray(8)
    REGx_MsgSend(request)
    return 0


def REGx_ReadModuleCount(dstAddr, device_code=REGx_DEVICE_CODE.SINGLE):
    request = REGx_Msg_t()
    request.errorCode = REGx_ERROR_CODE.NORMAL
    request.deviceCode = device_code
    request.cmdCode = 0x02
    request.dstAddr = dstAddr
    request.srcAddr = REGx_MASTER_ADDR
    request.data = bytearray(8)
    REGx_MsgSend(request)
    return 0


def REGx_ReadModuleVoltCurrFloat(dstAddr, device_code=REGx_DEVICE_CODE.SINGLE):
    request = REGx_Msg_t()
    request.errorCode = REGx_ERROR_CODE.NORMAL
    request.deviceCode = device_code
    request.cmdCode = 0x03
    request.dstAddr = dstAddr
    request.srcAddr = REGx_MASTER_ADDR
    request.data = bytearray(8)
    REGx_MsgSend(request)
    return 0


def REGx_ReadSystemVoltCurrFixed(dstAddr, device_code=REGx_DEVICE_CODE.SINGLE):
    request = REGx_Msg_t()
    request.errorCode = REGx_ERROR_CODE.NORMAL
    request.deviceCode = device_code
    request.cmdCode = 0x08
    request.dstAddr = dstAddr
    request.srcAddr = REGx_MASTER_ADDR
    request.data = bytearray(8)
    REGx_MsgSend(request)
    return 0


def REGx_ReadModuleParams(dstAddr, device_code=REGx_DEVICE_CODE.SINGLE):
    request = REGx_Msg_t()
    request.errorCode = REGx_ERROR_CODE.NORMAL
    request.deviceCode = device_code
    request.cmdCode = 0x0A
    request.dstAddr = dstAddr
    request.srcAddr = REGx_MASTER_ADDR
    request.data = bytearray(8)
    REGx_MsgSend(request)
    return 0


def REGx_ReadBarcode(dstAddr, device_code=REGx_DEVICE_CODE.SINGLE):
    request = REGx_Msg_t()
    request.errorCode = REGx_ERROR_CODE.NORMAL
    request.deviceCode = device_code
    request.cmdCode = 0x0B
    request.dstAddr = dstAddr
    request.srcAddr = REGx_MASTER_ADDR
    request.data = bytearray(8)
    REGx_MsgSend(request)
    return 0


def REGx_ReadExternalVoltCurr(dstAddr, device_code=REGx_DEVICE_CODE.SINGLE):
    request = REGx_Msg_t()
    request.errorCode = REGx_ERROR_CODE.NORMAL
    request.deviceCode = device_code
    request.cmdCode = 0x0C
    request.dstAddr = dstAddr
    request.srcAddr = REGx_MASTER_ADDR
    request.data = bytearray(8)
    REGx_MsgSend(request)
    return 0


def REGx_SetOutput(dstAddr, volt, curr, device_code=REGx_DEVICE_CODE.SINGLE):
    # Clamp voltage and current within their respective bounds
    volt = max(REGx_OUTPUT_DC_VOLT_MIN, min(volt, REGx_OUTPUT_DC_VOLT_MAX))
    curr = max(REGx_OUTPUT_DC_CURR_MIN, min(curr, REGx_OUTPUT_DC_CURR_MAX))

    request = REGx_Msg_t()

    request.errorCode = REGx_ERROR_CODE.NORMAL
    request.deviceCode = device_code
    request.cmdCode = 0x1C
    request.dstAddr = dstAddr
    request.srcAddr = REGx_MASTER_ADDR

    # Convert voltage and current to uint32_t representation
    voltSetValue = int(volt * 1000)
    currSetValue = int(curr * 1000)

    # Pack the data into big-endian format
    request.data[0] = (voltSetValue >> 24) & 0xFF
    request.data[1] = (voltSetValue >> 16) & 0xFF
    request.data[2] = (voltSetValue >> 8) & 0xFF
    request.data[3] = voltSetValue & 0xFF
    request.data[4] = (currSetValue >> 24) & 0xFF
    request.data[5] = (currSetValue >> 16) & 0xFF
    request.data[6] = (currSetValue >> 8) & 0xFF
    request.data[7] = currSetValue & 0xFF

    REGx_MsgSend(request)

    return 0


def REGx_Launch(dstAddr, device_code=REGx_DEVICE_CODE.SINGLE):
    request = REGx_Msg_t()

    request.errorCode = REGx_ERROR_CODE.NORMAL
    request.deviceCode = device_code
    request.cmdCode = 0x1A
    request.dstAddr = dstAddr
    request.srcAddr = REGx_MASTER_ADDR
    request.data[0] = 0x00  # Set launch command to ON

    REGx_MsgSend(request)

    return 0

def REGx_CloseOutput(dstAddr, device_code=REGx_DEVICE_CODE.SINGLE):
    request = REGx_Msg_t()

    REGx_CMD_CODE_LAUNCH_SET_ON = 0x00
    REGx_CMD_CODE_LAUNCH_SET_OFF = 0x01
    REGx_CMD_CODE_LAUNCH_SET = 0x1A

    request.errorCode = REGx_ERROR_CODE.NORMAL
    request.deviceCode = device_code
    request.cmdCode = REGx_CMD_CODE_LAUNCH_SET
    request.dstAddr = dstAddr
    request.srcAddr = REGx_MASTER_ADDR
    request.data[0] = REGx_CMD_CODE_LAUNCH_SET_OFF

    ret = REGx_MsgSend(request)

    return 0


def REGx_SetComprehensive(dstAddr, sub_cmd_hi: int, sub_cmd_lo: int, value: int, device_code=REGx_DEVICE_CODE.SINGLE):
    request = REGx_Msg_t()
    request.errorCode = REGx_ERROR_CODE.NORMAL
    request.deviceCode = device_code
    request.cmdCode = 0x0F
    request.dstAddr = dstAddr
    request.srcAddr = REGx_MASTER_ADDR
    request.data = bytearray(8)
    request.data[0] = sub_cmd_hi & 0xFF
    request.data[1] = sub_cmd_lo & 0xFF
    # data[2..6] 为协议保留字节，保持为 0
    request.data[7] = value & 0xFF
    REGx_MsgSend(request)
    return 0


def REGx_SetWalkIn(dstAddr, enable: bool, device_code=REGx_DEVICE_CODE.SINGLE):
    request = REGx_Msg_t()
    request.errorCode = REGx_ERROR_CODE.NORMAL
    request.deviceCode = device_code
    request.cmdCode = 0x13
    request.dstAddr = dstAddr
    request.srcAddr = REGx_MASTER_ADDR
    request.data = bytearray(8)
    request.data[0] = 0x01 if enable else 0x00
    REGx_MsgSend(request)
    return 0


def REGx_SetGreenLED(dstAddr, blink: bool, device_code=REGx_DEVICE_CODE.SINGLE):
    request = REGx_Msg_t()
    request.errorCode = REGx_ERROR_CODE.NORMAL
    request.deviceCode = device_code
    request.cmdCode = 0x14
    request.dstAddr = dstAddr
    request.srcAddr = REGx_MASTER_ADDR
    request.data = bytearray(8)
    request.data[0] = 0x01 if blink else 0x00
    REGx_MsgSend(request)
    return 0


def REGx_SetGroupNumber(dstAddr, group: int, device_code=REGx_DEVICE_CODE.SINGLE):
    request = REGx_Msg_t()
    request.errorCode = REGx_ERROR_CODE.NORMAL
    request.deviceCode = device_code
    request.cmdCode = 0x16
    request.dstAddr = dstAddr
    request.srcAddr = REGx_MASTER_ADDR
    request.data = bytearray(8)
    request.data[0] = group & 0xFF
    REGx_MsgSend(request)
    return 0


def REGx_SetSleep(dstAddr, sleep: bool, device_code=REGx_DEVICE_CODE.SINGLE):
    request = REGx_Msg_t()
    request.errorCode = REGx_ERROR_CODE.NORMAL
    request.deviceCode = device_code
    request.cmdCode = 0x19
    request.dstAddr = dstAddr
    request.srcAddr = REGx_MASTER_ADDR
    request.data = bytearray(8)
    request.data[0] = 0x01 if sleep else 0x00
    REGx_MsgSend(request)
    return 0


def REGx_SetSystemOutput(dstAddr, volt: float, total_curr: float, device_code=REGx_DEVICE_CODE.SINGLE):
    volt = max(REGx_OUTPUT_DC_VOLT_MIN, min(volt, REGx_OUTPUT_DC_VOLT_MAX))
    total_curr = max(0.0, total_curr)  # 系统总电流不设上限（多模块并联可超过单模块最大值）
    request = REGx_Msg_t()
    request.errorCode = REGx_ERROR_CODE.NORMAL
    request.deviceCode = device_code
    request.cmdCode = 0x1B
    request.dstAddr = dstAddr
    request.srcAddr = REGx_MASTER_ADDR
    request.data = bytearray(8)
    voltSetValue = int(volt * 1000)
    currSetValue = int(total_curr * 1000)
    request.data[0] = (voltSetValue >> 24) & 0xFF
    request.data[1] = (voltSetValue >> 16) & 0xFF
    request.data[2] = (voltSetValue >> 8) & 0xFF
    request.data[3] = voltSetValue & 0xFF
    request.data[4] = (currSetValue >> 24) & 0xFF
    request.data[5] = (currSetValue >> 16) & 0xFF
    request.data[6] = (currSetValue >> 8) & 0xFF
    request.data[7] = currSetValue & 0xFF
    REGx_MsgSend(request)
    return 0


def REGx_SetAddressMode(dstAddr, dip_switch: bool, device_code=REGx_DEVICE_CODE.SINGLE):
    request = REGx_Msg_t()
    request.errorCode = REGx_ERROR_CODE.NORMAL
    request.deviceCode = device_code
    request.cmdCode = 0x1F
    request.dstAddr = dstAddr
    request.srcAddr = REGx_MASTER_ADDR
    request.data = bytearray(8)
    request.data[0] = 0x01 if dip_switch else 0x00
    REGx_MsgSend(request)
    return 0


def REGx_SetLiquidCoolTemp(dstAddr, tin: int, tout: int, tamb: int, device_code=REGx_DEVICE_CODE.SINGLE):
    # 协议 0x0F sub_cmd 0x13 0x01：进水口/出水口/环温（单字节有符号数，& 0xFF 转补码）
    req = REGx_Msg_t()
    req.errorCode = REGx_ERROR_CODE.NORMAL
    req.deviceCode = device_code
    req.cmdCode = 0x0F
    req.dstAddr = dstAddr
    req.srcAddr = REGx_MASTER_ADDR
    req.data = bytearray(8)
    req.data[0] = 0x13
    req.data[1] = 0x01
    # data[2..4] reserved，保持为 0
    req.data[5] = tin & 0xFF
    req.data[6] = tout & 0xFF
    req.data[7] = tamb & 0xFF
    REGx_MsgSend(req)
    return 0


last_request_time = 0
request_list = [lambda : REGx_ReadStateRequest(0x00),
                lambda : REGx_ReadInputRequest(0x00),
                lambda : REGx_ReadOutputRequest(0x00)]
request_idx = 0

def REGx_Poll(can_msg_list1, canController_info: CANControllerInfo):
    global last_request_time, request_idx, request_list
    if time.time() - last_request_time > 0.5:
        request_list[request_idx]()
        request_idx = (request_idx + 1) % len(request_list)
        last_request_time = time.time()

    for can_msg in can_msg_list1:
        # print(len(can_msg.data), can_msg.data)
        REGx_CAN_ReceviceCallback(can_msg, canController_info)

def REGx_CAN_ReceviceCallback(can_msg,canController_info:CANControllerInfo):

    RxData = bytearray(8)
    l_response = REGx_Msg_t()
    Identifier = can_msg.can_id
    RxData[:] = can_msg.data
    # Retrieve Rx messages from RX FIFO0
    response = l_response
    # Decode received data
    response.errorCode = (Identifier >> 26) & 0x07
    response.deviceCode = (Identifier >> 22) & 0x0F
    response.cmdCode = (Identifier >> 16) & 0x3F
    response.dstAddr = (Identifier >> 8) & 0xFF
    response.srcAddr = Identifier & 0xFF
    response.data[:] = RxData[:]

    formatted_identifier = f"({Identifier >> 24:02X} {Identifier >> 16 & 0xFF:02X} {Identifier >> 8 & 0xFF:02X} {Identifier & 0xFF:02X})"
    print(f"<== Identifier: {formatted_identifier} TxData: {RxData}")

    if g_log_callback:
        g_log_callback('RX', Identifier, bytes(RxData), "")

    if (response.dstAddr == REGx_MASTER_ADDR or response.dstAddr == REGx_BROADCAST_ADDR):
        if (response.cmdCode == 0x04):
            canController_info.Temperature = response.data[4]
        elif (response.cmdCode == 0x06):
            '''
            交流 AB
            电 压 高
            字节（单
            相 输 入
            电 压 高
            字节） 
            交流 AB
            电压低
            字 节
            （单相
            输入电
            压低字
            节） 
            交流 BC
            电压高
            字节 
            交流 BC
            电压低
            字节 
            交流 CA
            电压高
            字 节
            （直流
            输入电
            压高字
            节） 
            交流 CA
            电压低
            字 节
            （直流
            输入电
            压低字
            节） 
            0 0 

            '''
            canController_info.AC_AB_Volt = (response.data[0] << 8) | response.data[1]
            canController_info.AC_BC_Volt = (response.data[2] << 8) | response.data[3]
            canController_info.AC_CA_Volt = (response.data[4] << 8) | response.data[5]

            canController_info.AC_AB_Volt = canController_info.AC_AB_Volt * 0.1
            canController_info.AC_BC_Volt = canController_info.AC_BC_Volt * 0.1
            canController_info.AC_CA_Volt = canController_info.AC_CA_Volt * 0.1

        elif (response.cmdCode == 0x09):
            '''
            模块 N 电压（mV） 模块 N 电流（mA） 
            MSB MSB MSB MSB
            模块回复： 02 89 F0 00 00 03 0D 40 00 00 13 88——0#模块回复电压 200V，电流 5A
            '''
            canController_info.DC_Output_Volt = (response.data[0] << 24) | (response.data[1] << 16) | (response.data[2] << 8) | response.data[3]
            canController_info.DC_Output_Curr = (response.data[4] << 24) | (response.data[5] << 16) | (response.data[6] << 8) | response.data[7]

            canController_info.DC_Output_Volt = canController_info.DC_Output_Volt / 1000
            canController_info.DC_Output_Curr = canController_info.DC_Output_Curr / 1000
            canController_info.DC_Output_Power = canController_info.DC_Output_Volt * canController_info.DC_Output_Curr

            if canController_info.DC_Output_Volt > 5:
                canController_info.ChargerState = 1
            else:
                canController_info.ChargerState = 0

        elif response.cmdCode == 0x01:
            canController_info.SystemVolt = struct.unpack('>f', bytes(response.data[0:4]))[0]
            canController_info.SystemCurr = struct.unpack('>f', bytes(response.data[4:8]))[0]
        elif response.cmdCode == 0x02:
            # 协议定义：Byte0=0, Byte1=0, Byte2=模块数量（参见 2.4 节 0x02 回复格式）
            canController_info.ModuleCount = response.data[2]
        elif response.cmdCode == 0x03:
            canController_info.ModuleVoltFloat = struct.unpack('>f', bytes(response.data[0:4]))[0]
            canController_info.ModuleCurrFloat = struct.unpack('>f', bytes(response.data[4:8]))[0]
        elif response.cmdCode == 0x08:
            canController_info.SystemVolt = ((response.data[0] << 24) | (response.data[1] << 16) |
                                             (response.data[2] << 8) | response.data[3]) / 1000.0
            # 协议保证电流值非负（无符号整数，单位 mA），直接除以 1000 转换为 A
            canController_info.SystemCurr = ((response.data[4] << 24) | (response.data[5] << 16) |
                                             (response.data[6] << 8) | response.data[7]) / 1000.0
        elif response.cmdCode == 0x0A:
            # 0x0A 回复：电压单位 V（整数），电流单位 0.1A，功率单位 10W（参见协议 2.4 节）
            canController_info.ParamVoltMax = float((response.data[0] << 8) | response.data[1])
            canController_info.ParamVoltMin = float((response.data[2] << 8) | response.data[3])
            canController_info.ParamCurrMax = ((response.data[4] << 8) | response.data[5]) * 0.1
            canController_info.ParamPower = ((response.data[6] << 8) | response.data[7]) * 10.0
        elif response.cmdCode == 0x0B:
            canController_info.Barcode = ' '.join(f'{b:02X}' for b in response.data)
        elif response.cmdCode == 0x0C:
            canController_info.ExternalVolt = ((response.data[0] << 8) | response.data[1]) * 0.1
            canController_info.AllowedCurr = ((response.data[2] << 8) | response.data[3]) * 0.1
        else:
            pass
