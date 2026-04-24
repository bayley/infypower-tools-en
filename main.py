import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QIcon
from PyQt5.QtWidgets import (QAction, QApplication, QFrame, QHBoxLayout,
                              QMenu, QSystemTrayIcon, QWidget)
from qfluentwidgets import (Action, AvatarWidget, BodyLabel, CaptionLabel,
                             FluentIcon, FluentIcon as FIF, FluentWindow,
                             HyperlinkButton, MessageBox, NavigationAvatarWidget,
                             NavigationItemPosition, SwitchButton,
                             Theme, isDarkTheme, setFont, setTheme, setThemeColor)
from qfluentwidgets.components.material import AcrylicMenu

from config_manager import AppConfig, ConfigManager
from HDL_CAN import CANDev
from home_widget import GroupHomeWidget
from manual_widget import ManualWidget
from REG1K0100A2 import CANControllerInfo, REGx_Init


class SettingWidget(QFrame):
    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)
        self.hBoxLayout = QHBoxLayout(self)
        self.switchButton = SwitchButton(self)
        self.switchButton.setOnText('Dark')
        self.switchButton.setOffText('Light')
        self.switchButton.checkedChanged.connect(
            lambda: setTheme(Theme.DARK if self.switchButton.isChecked() else Theme.LIGHT))
        setFont(self.switchButton, 24)
        self.hBoxLayout.addWidget(self.switchButton, 1, Qt.AlignCenter)
        self.setObjectName(text.replace(' ', '-'))


class ProfileCard(QWidget):
    def __init__(self, avatarPath: str, name: str, email: str, parent=None):
        super().__init__(parent=parent)
        self.avatar = AvatarWidget(avatarPath, self)
        self.nameLabel = BodyLabel(name, self)
        self.emailLabel = CaptionLabel(email, self)
        self.logoutButton = HyperlinkButton(
            'https://github.com/MisakaMikoto128', '注销', self)
        color = QColor(206, 206, 206) if isDarkTheme() else QColor(96, 96, 96)
        self.emailLabel.setStyleSheet('QLabel{color: ' + color.name() + '}')
        color = QColor(255, 255, 255) if isDarkTheme() else QColor(0, 0, 0)
        self.nameLabel.setStyleSheet('QLabel{color: ' + color.name() + '}')
        setFont(self.logoutButton, 13)
        self.setFixedSize(307, 82)
        self.avatar.setRadius(24)
        self.avatar.move(2, 6)
        self.nameLabel.move(64, 13)
        self.emailLabel.move(64, 32)
        self.logoutButton.move(52, 48)


class Window(FluentWindow):
    def __init__(self):
        super().__init__()
        setThemeColor('#28afe9')

        self._config = ConfigManager().load()

        self.can_device = CANDev()
        REGx_Init(self.can_device)
        self.canController_info = CANControllerInfo()  # 仅供 manual_widget 使用

        self.homeInterface = GroupHomeWidget(
            can_device=self.can_device,
            config=self._config,
            parent=self,
        )
        self.homeInterface.setObjectName('GroupHomeWidget')
        self.manualInterface = ManualWidget(
            can_device=self.can_device,
            canController_info=self.canController_info,
            config=self._config,
            parent=self,
        )
        self.settingInterface = SettingWidget('Setting Interface', self)

        self.setWindowState(Qt.WindowMaximized)
        self._init_navigation()
        self._init_window()

        # Tray
        exitAction = QAction(QIcon('./img/sp-exit.png'), 'Exit', self)
        exitAction.triggered.connect(self.close)
        trayMenu = QMenu(self)
        trayMenu.addAction(exitAction)
        self.trayIcon = QSystemTrayIcon(self)
        self.trayIcon.setIcon(QIcon('./img/star.png'))
        self.trayIcon.setContextMenu(trayMenu)
        self.trayIcon.show()

    def _init_navigation(self):
        self.addSubInterface(self.homeInterface, FIF.HOME, '主页')
        self.addSubInterface(self.manualInterface, FIF.EDIT, '手动操作')
        self.navigationInterface.addSeparator()
        self.navigationInterface.addWidget(
            routeKey='avatar',
            widget=NavigationAvatarWidget('Yuanlin-Liu', 'resource/shoko.png'),
            onClick=self._show_about,
            position=NavigationItemPosition.BOTTOM,
        )
        self.addSubInterface(self.settingInterface, FIF.SETTING, 'Settings',
                             NavigationItemPosition.BOTTOM)
        self.navigationInterface.setAcrylicEnabled(True)

    def _init_window(self):
        self.resize(1100, 760)
        self.setWindowTitle(self._config.device_name)
        self.setWindowIcon(QIcon('./img/star.png'))
        desktop = QApplication.desktop().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)

    def _show_about(self):
        MessageBox('支持作者', '🥤🥤🚀', self).exec()

    def contextMenuEvent(self, e) -> None:
        menu = AcrylicMenu(parent=self)
        card = ProfileCard('resource/shoko.png', '刘沅林',
                           'liuyuanlins@outlook.com', menu)
        menu.addWidget(card, selectable=False)
        menu.addSeparator()
        menu.addActions([
            Action(FluentIcon.PEOPLE, '管理账户和设置'),
            Action(FluentIcon.SHOPPING_CART, '支付方式'),
            Action(FluentIcon.CODE, '兑换代码和礼品卡'),
        ])
        menu.addSeparator()
        menu.addAction(Action(FluentIcon.SETTING, '设置'))
        menu.exec(e.globalPos())

    def closeEvent(self, event):
        self.can_device.close_device()
        event.accept()


if __name__ == '__main__':
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    app = QApplication(sys.argv)
    w = Window()
    w.show()
    app.exec_()
