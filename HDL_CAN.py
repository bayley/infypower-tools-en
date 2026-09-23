# python3.8.0 64位（python 32位要用32位的DLL）
from ctypes import *
import ctypes
from typing import Optional, Tuple, List, Any

VCI_USBCAN2 = 4
STATUS_OK = 1


class VCI_INIT_CONFIG(Structure):
    _fields_ = [("AccCode", c_uint),
                ("AccMask", c_uint),
                ("Reserved", c_uint),
                ("Filter", c_ubyte),
                ("Timing0", c_ubyte),
                ("Timing1", c_ubyte),
                ("Mode", c_ubyte)
                ]


class VCI_CAN_OBJ(Structure):
    _fields_ = [("ID", c_uint),
                ("TimeStamp", c_uint),
                ("TimeFlag", c_ubyte),
                ("SendType", c_ubyte),
                ("RemoteFlag", c_ubyte),
                ("ExternFlag", c_ubyte),
                ("DataLen", c_ubyte),
                ("Data", c_ubyte * 8),
                ("Reserved", c_ubyte * 3)
                ]


"""
typedef struct _VCI_BOARD_INFO {
USHORT hw_Version;
USHORT fw_Version;
USHORT dr_Version;
USHORT in_Version;
USHORT irq_Num;
BYTE can_Num;
CHAR str_Serial_Num[20];
CHAR str_hw_Type[40];
USHORT Reserved[4];
} VCI_BOARD_INFO, *PVCI_BOARD_INFO;
"""


class VCI_BOARD_INFO(Structure):
    _fields_ = [("hw_Version", c_ushort),
                ("fw_Version", c_ushort),
                ("dr_Version", c_ushort),
                ("in_Version", c_ushort),
                ("irq_Num", c_ushort),
                ("can_Num", c_ubyte),
                ("str_Serial_Num", c_char * 20),
                ("str_hw_Type", c_char * 40),
                ("Reserved", c_ushort * 4)
                ]


class CANMsg:
    def __init__(self):
        self.can_id = 0
        self.data = b''


class VCI_CAN_OBJ_ARRAY(Structure):
    _fields_ = [('SIZE', ctypes.c_uint16), ('STRUCT_ARRAY', ctypes.POINTER(VCI_CAN_OBJ))]

    def __init__(self, num_of_structs):
        # 这个括号不能少
        self.STRUCT_ARRAY = ctypes.cast((VCI_CAN_OBJ * num_of_structs)(), ctypes.POINTER(VCI_CAN_OBJ))  # 结构体数组
        self.SIZE = num_of_structs  # 结构体长度
        self.ADDR = self.STRUCT_ARRAY[0]  # 结构体数组地址  byref()转c地址


class CANDev:
    def __init__(self):
        self.CanDLLName = './ControlCAN.dll'  # 把DLL放到对应的目录下
        self.canDLL = windll.LoadLibrary('./ControlCAN.dll')
        # Linux系统下使用下面语句，编译命令：python3 python3.8.0.py
        # canDLL = cdll.LoadLibrary('./libcontrolcan.so')
        self.VCI_USBCAN2 = 4
        self.STATUS_OK = 1
        self.VCI_INIT_CONFIG = VCI_INIT_CONFIG
        self.isCanOpen = False
        self.rx_vci_can_obj = VCI_CAN_OBJ_ARRAY(2500)  # 结构体数组

    def open_device(self):
        ret = self.canDLL.VCI_OpenDevice(self.VCI_USBCAN2, 0, 0)
        if ret == self.STATUS_OK:
            print('VCI_OpenDevice succeeded')
        if ret != self.STATUS_OK:
            print('VCI_OpenDevice failed')
            return False

        # 初始0通道
        self.vci_initconfig = VCI_INIT_CONFIG(0x80000008, 0xFFFFFFFF, 0,
                                              0, 0x03, 0x1C, 0)  # 波特率125k，正常模式
        ret = self.canDLL.VCI_InitCAN(VCI_USBCAN2, 0, 0, byref(self.vci_initconfig))
        if ret == STATUS_OK:
            print('VCI_InitCAN1 succeeded')
        if ret != STATUS_OK:
            print('VCI_InitCAN1 failed')
            return False

        ret = self.canDLL.VCI_StartCAN(VCI_USBCAN2, 0, 0)
        if ret == STATUS_OK:
            print('VCI_StartCAN1 succeeded')
        if ret != STATUS_OK:
            print('VCI_StartCAN1 failed')
            return False

        # 初始1通道
        ret = self.canDLL.VCI_InitCAN(VCI_USBCAN2, 0, 1, byref(self.vci_initconfig))
        if ret == STATUS_OK:
            print('VCI_InitCAN2 succeeded')
        if ret != STATUS_OK:
            print('VCI_InitCAN2 failed')
            return False

        ret = self.canDLL.VCI_StartCAN(VCI_USBCAN2, 0, 1)
        if ret == STATUS_OK:
            print('VCI_StartCAN2 succeeded')
        if ret != STATUS_OK:
            print('VCI_StartCAN2 failed')
            return False

        self.isCanOpen = True
        return True

    def close_device(self):
        self.canDLL.VCI_CloseDevice(VCI_USBCAN2, 0)
        self.isCanOpen = False

    def send_data(self, channel: int, can_id: int, data: bytes):
        if not self.isCanOpen:
            return

        if not (channel == 0 or channel == 1):
            return

        can_id = can_id & 0x1FFFFFFF

        externFlag = 0
        if can_id > 0x7FF:
            externFlag = 1

        ubyte_array = c_ubyte * len(data)
        bytes_data = ubyte_array(*data)
        ubyte_3array = c_ubyte * 3
        reserved = ubyte_3array(0, 0, 0)
        vci_can_obj = VCI_CAN_OBJ(can_id, 0, 0, 1, 0, externFlag, len(data), bytes_data, reserved)
        ret = self.canDLL.VCI_Transmit(VCI_USBCAN2, 0, channel, byref(vci_can_obj), 1)
        if ret != STATUS_OK:
            print(f'CAN{channel + 1} channel send failed')

    def send_data_ch1(self, can_id: int, data: bytes):
        self.send_data(0, can_id, data)

    def send_data_ch2(self, can_id: int, data: bytes):
        self.send_data(1, can_id, data)

    def read_ch(self, channel: int) -> Tuple[List[CANMsg], Any]:
        ret = self.canDLL.VCI_Receive(VCI_USBCAN2, 0, channel, byref(self.rx_vci_can_obj.ADDR), 2500, 0)
        can_msg_list = []

        if ret > 0:
            for i in range(ret):
                can_msg = CANMsg()
                can_id = self.rx_vci_can_obj.STRUCT_ARRAY[i].ID
                # 转换为VCI_CAN_OBJ的ID成员为python的int
                can_msg.can_id = int(can_id)
                can_msg.data = bytes(list(self.rx_vci_can_obj.STRUCT_ARRAY[i].Data))
                can_msg_list.append(can_msg)

        return can_msg_list, ret

    def read_ch1(self) -> list:
        return self.read_ch(0)

    def read_ch2(self) -> list:
        return self.read_ch(1)

    def findUsbDevice2(self):
        # Create an array of VCI_BOARD_INFO structures
        pInfoArrayType = VCI_BOARD_INFO * 50
        pInfoArray = pInfoArrayType()

        # Call the function with pInfoArray
        num = self.canDLL.VCI_FindUsbDevice2(pInfoArray)

        return num
