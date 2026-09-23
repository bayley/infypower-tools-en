@echo off
chcp 65001 > nul
echo "============================================================"
echo "    REG1K0100A2 Charging Module Host Computer Nuitka DEBUG Packaging"
echo "    * CMD window remains visible for easy startup error viewing"
echo "    * Disable LTO and -OO, preserve debug info, faster compilation"
echo "============================================================"
echo ""

cd /d "%~dp0"

python --version > nul 2>&1
if errorlevel 1 (
    echo "[ERROR] Python not found, please confirm it is added to PATH."
    pause & exit /b 1
)

if exist .venv\Scripts\activate.bat (
    echo "[INFO]  Activating virtual environment .venv ..."
    call .venv\Scripts\activate.bat
) else if exist venv\Scripts\activate.bat (
    echo "[INFO]  Activating virtual environment venv ..."
    call venv\Scripts\activate.bat
) else (
    echo "[WARN]  Virtual environment not found, using system Python."
)

python -c "import nuitka" > nul 2>&1
if errorlevel 1 (
    echo "[INFO]  Installing Nuitka ..."
    pip install nuitka
    if errorlevel 1 ( echo "[ERROR] Nuitka installation failed!" & pause & exit /b 1 )
)

set NUITKA_CACHE_DIR_DOWNLOADS=.build_cache\nuitka_downloads
set NUITKA_CACHE_DIR_CCACHE=.build_cache\nuitka_ccache
set NUITKA_CACHE_DIR_CLCACHE=.build_cache\nuitka_clcache
set NUITKA_CACHE_DIR_BYTECODE=.build_cache\nuitka_bytecode
set NUITKA_CACHE_DIR_DLL_DEPENDENCIES=.build_cache\nuitka_dll_dep

set PYTHONUNBUFFERED=1
set start_time=%time%
echo ""
echo "[INFO]  Starting DEBUG packaging... %start_time%"
echo "[INFO]  Output directory: release\main.dist\"
echo ""

python -m nuitka ^
    --msvc=latest ^
    --standalone ^
    --assume-yes-for-downloads ^
    --follow-imports ^
    --windows-console-mode=attach ^
    --windows-icon-from-ico=img\star.ico ^
    --windows-company-name="INFYPOWER" ^
    --windows-product-name="REG1K0100A2 Charging Module Host Computer [DEBUG]" ^
    --windows-file-version=0.0.0.1 ^
    --windows-product-version=0.0.0.1 ^
    --windows-file-description="REG1K0100A2 Charging Module Host Computer DEBUG" ^
    --python-flag=no_site ^
    --enable-plugin=pyqt5 ^
    --enable-plugin=multiprocessing ^
    --enable-plugin=anti-bloat ^
    --include-package=qfluentwidgets ^
    --include-package-data=qfluentwidgets ^
    --include-package=qframelesswindow ^
    --include-package=qframelesswindow.titlebar ^
    --include-package-data=qframelesswindow ^
    --include-package=can ^
    --include-data-files=ControlCAN.dll=ControlCAN.dll ^
    --include-data-dir=img=img ^
    --include-data-dir=resource=resource ^
    --nofollow-import-to=setuptools,pip,wheel ^
    --nofollow-import-to=pytest,docutils,unittest ^
    --nofollow-import-to=matplotlib,scipy,pandas,openpyxl ^
    --nofollow-import-to=numba,llvmlite ^
    --nofollow-import-to=pyqtgraph,OpenGL ^
    --nofollow-import-to=numpy ^
    --nofollow-import-to=PyQt5.Qt3DAnimation ^
    --nofollow-import-to=PyQt5.Qt3DCore ^
    --nofollow-import-to=PyQt5.Qt3DExtras ^
    --nofollow-import-to=PyQt5.Qt3DInput ^
    --nofollow-import-to=PyQt5.Qt3DLogic ^
    --nofollow-import-to=PyQt5.Qt3DRender ^
    --nofollow-import-to=PyQt5.QtBluetooth ^
    --nofollow-import-to=PyQt5.QtDesigner ^
    --nofollow-import-to=PyQt5.QtHelp ^
    --nofollow-import-to=PyQt5.QtLocation ^
    --nofollow-import-to=PyQt5.QtMultimedia ^
    --nofollow-import-to=PyQt5.QtMultimediaWidgets ^
    --nofollow-import-to=PyQt5.QtNfc ^
    --nofollow-import-to=PyQt5.QtPositioning ^
    --nofollow-import-to=PyQt5.QtQml ^
    --nofollow-import-to=PyQt5.QtQuick ^
    --nofollow-import-to=PyQt5.QtRemoteObjects ^
    --nofollow-import-to=PyQt5.QtSensors ^
    --nofollow-import-to=PyQt5.QtSerialPort ^
    --nofollow-import-to=PyQt5.QtSql ^
    --nofollow-import-to=PyQt5.QtTest ^
    --nofollow-import-to=PyQt5.QtWebChannel ^
    --nofollow-import-to=PyQt5.QtWebEngine ^
    --nofollow-import-to=PyQt5.QtWebEngineCore ^
    --nofollow-import-to=PyQt5.QtWebEngineWidgets ^
    --nofollow-import-to=PyQt5.QtWebSockets ^
    --nofollow-import-to=*.tests ^
    --nofollow-import-to=*.test ^
    --nofollow-import-to=*.testing ^
    --output-filename=INFY_POWER_debug.exe ^
    --output-dir=release ^
    main.py

echo ""
echo "[INFO]  DEBUG packaging completed %time% (started %start_time%)"

if errorlevel 1 (
    echo "[ERROR] Packaging failed!"
    pause & exit /b 1
)

if exist config.json (
    copy /y config.json release\main.dist\config.json > nul
    echo "[INFO]  config.json copied"
)

echo ""
echo "============================================================"
echo "  DEBUG packaging successful!"
echo "  Execute release\main.dist\INFY_POWER_debug.exe"
echo "  CMD window will remain visible on startup, print / traceback visible."
echo "============================================================"
pause