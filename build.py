#!/usr/bin/env python3
"""
REG1K0100A2 充电模块上位机 - Nuitka Build Script
=======================================================
Usage:
    python build.py [folder|onefile]

Modes:
    folder    Compile to a standalone directory (DEFAULT — required for DLL)
    onefile   Compile to a single self-contained .exe
              WARNING: ControlCAN.dll is loaded via './ControlCAN.dll' (cwd-relative).
              In onefile mode the working directory is where the user launches the exe,
              so the DLL must be placed alongside the exe manually after packaging.

Features:
    - Auto version from git tag, fallback to date-based string
    - Parallel C compilation (all CPU cores)
    - Size optimisation: exclude unused Qt / Python modules
    - Bundles ControlCAN.dll, img/ and resource/ as data files
    - Writes Windows PE version resource
    - Optional self-signed code signing via signtool + PowerShell cert
    - Artifacts land in  release/v<version>/
"""

import subprocess
import sys
import os
import shutil
import multiprocessing
from pathlib import Path
from datetime import datetime
from typing import Optional, List

# ── Paths ─────────────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).parent.resolve()
MAIN_SCRIPT  = SCRIPT_DIR / 'main.py'
BUILD_CACHE  = SCRIPT_DIR / '.build_cache'
RELEASE_ROOT = SCRIPT_DIR / 'release'
CERT_PFX     = SCRIPT_DIR / 'build_sign.pfx'

# ── App metadata ──────────────────────────────────────────────
APP_NAME      = 'INFY_POWER'
APP_DESC      = 'REG1K0100A2 Charging Module Host Controller'
APP_COMPANY   = 'INFYPOWER'
APP_COPYRIGHT = f'Copyright 2024-{datetime.now().year} INFYPOWER'
# Files / dirs copied alongside exe in the release folder
CONFIG_FILES  = ['config.json']          # auto-generated on first run; copied if present
DATA_FILES    = ['ControlCAN.dll']       # CAN hardware driver DLL (required at runtime)
DATA_DIRS     = ['img', 'resource']      # icons and avatars

# ── Code-signing ──────────────────────────────────────────────
CERT_PWD = 'INFY_POWER_Build_Sign!'
TIMESTAMP_SERVERS: List[str] = [
    'http://timestamp.digicert.com',
    'http://timestamp.sectigo.com',
    'http://timestamp.comodoca.com',
]

# ─────────────────────────────────────────────────────────────


def log(level: str, msg: str):
    prefix = {'INFO': '[INFO]', 'WARN': '[WARN]', 'ERROR': '[ERROR]'}.get(level, '[    ]')
    print(f'{prefix} {msg}', flush=True)


# ── Nuitka ────────────────────────────────────────────────────

def ensure_nuitka():
    r = subprocess.run(
        [sys.executable, '-m', 'nuitka', '--version'],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        ver = r.stdout.strip().split('\n')[0]
        log('INFO', f'Nuitka {ver}')
    else:
        log('INFO', 'Nuitka not found — installing from PyPI...')
        subprocess.run(
            [sys.executable, '-m', 'pip', 'install', 'nuitka', '--quiet'],
            check=True,
        )
        log('INFO', 'Nuitka installed.')


# ── Version helpers ───────────────────────────────────────────

def get_version() -> str:
    try:
        r = subprocess.run(
            ['git', 'describe', '--tags', '--abbrev=0'],
            capture_output=True, text=True, cwd=SCRIPT_DIR,
        )
        if r.returncode == 0:
            tag = r.stdout.strip().lstrip('v')
            log('INFO', f'Version from git tag: {tag}')
            return tag
    except FileNotFoundError:
        pass
    ver = f'0.1.{datetime.now().strftime("%Y%m%d")}'
    log('INFO', f'No git tag — using date version: {ver}')
    return ver


def to_win_version(version: str) -> str:
    base = version.split('-')[0]
    parts = base.split('.')
    nums: List[str] = []
    for p in parts:
        try:
            n = int(p)
            if n <= 65535:
                nums.append(str(n))
            else:
                nums.append(str(n // 10000))
                nums.append(str(n % 10000))
        except ValueError:
            nums.append('0')
        if len(nums) >= 4:
            break
    while len(nums) < 4:
        nums.append('0')
    return '.'.join(nums[:4])


# ── Code signing ──────────────────────────────────────────────

def find_signtool() -> Optional[str]:
    path = shutil.which('signtool')
    if path:
        return path
    kits = Path(r'C:\Program Files (x86)\Windows Kits\10\bin')
    if kits.exists():
        candidates = sorted(
            kits.glob('*/x64/signtool.exe'),
            key=lambda p: p.parts[-3],
            reverse=True,
        )
        if candidates:
            return str(candidates[0])
    return None


def create_cert() -> bool:
    ps_cmd = (
        f"$pwd = ConvertTo-SecureString -String '{CERT_PWD}' -Force -AsPlainText; "
        f"$cert = New-SelfSignedCertificate "
        f"-Type CodeSigning "
        f"-Subject 'CN={APP_COMPANY}, O={APP_COMPANY}, C=CN' "
        f"-CertStoreLocation 'Cert:\\CurrentUser\\My' "
        f"-NotAfter (Get-Date).AddYears(5) "
        f"-HashAlgorithm SHA256; "
        f"Export-PfxCertificate -Cert $cert "
        f"-FilePath '{CERT_PFX}' -Password $pwd | Out-Null; "
        f"Write-Host 'CERT_OK:' $cert.Thumbprint"
    )
    try:
        r = subprocess.run(
            ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', ps_cmd],
            capture_output=True, text=True, timeout=30,
        )
        ok = r.returncode == 0 and CERT_PFX.exists()
        if ok:
            log('INFO', 'Self-signed certificate created.')
        else:
            log('WARN', f'Certificate creation: {r.stdout.strip()} {r.stderr.strip()}')
        return ok
    except Exception as exc:
        log('WARN', f'Certificate creation exception: {exc}')
        return False


def sign_exe(exe: Path):
    if not exe.exists():
        log('WARN', f'Sign target not found: {exe}')
        return
    print()
    log('INFO', f'Code signing: {exe.name}')
    signtool = find_signtool()
    if not signtool:
        log('WARN', 'signtool.exe not found — executable will be UNSIGNED.')
        return
    if not CERT_PFX.exists():
        if not create_cert():
            log('WARN', 'Skipping code signing.')
            return
    base_args = [signtool, 'sign', '/f', str(CERT_PFX), '/p', CERT_PWD,
                 '/fd', 'SHA256', '/d', APP_DESC]
    for ts in TIMESTAMP_SERVERS:
        r = subprocess.run(base_args + ['/tr', ts, '/td', 'SHA256', str(exe)],
                           capture_output=True, text=True)
        if r.returncode == 0:
            log('INFO', f'Signed with timestamp: {ts}')
            return
        log('WARN', f'Timestamp {ts} failed.')
    r = subprocess.run(base_args + [str(exe)], capture_output=True, text=True)
    if r.returncode == 0:
        log('INFO', 'Signed (no timestamp).')
    else:
        log('WARN', f'Signing failed: {r.stderr.strip()[:200]}')


# ── Build ─────────────────────────────────────────────────────

def build(mode: str):
    version   = get_version()
    win_ver   = to_win_version(version)
    cpu_cores = multiprocessing.cpu_count()

    exe_name    = f'{APP_NAME}.exe'
    folder_name = f'{APP_NAME}_v{version}'
    release_dir = RELEASE_ROOT / f'v{version}'
    release_dir.mkdir(parents=True, exist_ok=True)
    BUILD_CACHE.mkdir(parents=True, exist_ok=True)

    print()
    print('=' * 60)
    print(f'  {APP_DESC}  Build System')
    print(f'  Mode    : {mode}')
    print(f'  Version : {version}')
    print(f'  WinVer  : {win_ver}')
    print(f'  Cores   : {cpu_cores}')
    print(f'  Output  : {release_dir}')
    print('=' * 60)
    print()

    if mode == 'onefile':
        log('WARN', 'onefile mode: ControlCAN.dll must be placed next to the exe manually.')
        log('WARN', '              HDL_CAN.py loads "./ControlCAN.dll" relative to cwd.')

    # ── Nuitka command ────────────────────────────────────────
    cmd = [
        sys.executable, '-m', 'nuitka',

        '--assume-yes-for-downloads',
        '--follow-imports',
        f'--output-dir={BUILD_CACHE}',
        f'--jobs={cpu_cores}',

        # Suppress console window (GUI app)
        '--windows-console-mode=disable',

        # PyQt5 plugin — handles Qt DLLs, plugins, translations automatically
        '--enable-plugins=pyqt5',
        # multiprocessing support (used indirectly by some Qt / Python internals)
        '--enable-plugins=multiprocessing',
        # Anti-bloat: removes accidental heavy imports (tkinter, IPython, etc.)
        '--enable-plugins=anti-bloat',
        # Link-time optimisation — reduces binary size
        '--lto=yes',

        # Windows PE version resource
        f'--company-name={APP_COMPANY}',
        f'--product-name={APP_NAME}',
        f'--file-version={win_ver}',
        f'--product-version={win_ver}',
        f'--file-description={APP_DESC}',
        f'--copyright={APP_COPYRIGHT}',

        # ── General size optimisations ────────────────────────
        '--python-flag=no_site',
        '--python-flag=-OO',        # strip docstrings, optimise bytecode

        # Exclude heavy dev/test frameworks (anti-bloat plugin mode flags)
        '--noinclude-pytest-mode=nofollow',
        '--noinclude-unittest-mode=nofollow',
        '--noinclude-setuptools-mode=nofollow',
        '--noinclude-IPython-mode=nofollow',
        '--noinclude-dask-mode=nofollow',
        '--noinclude-numba-mode=nofollow',
        '--noinclude-pydoc-mode=nofollow',

        # Exclude unused Python packages (not used by this project)
        '--nofollow-import-to=setuptools,pip,wheel',
        '--nofollow-import-to=pytest,docutils,unittest',
        '--nofollow-import-to=matplotlib,scipy,pandas,openpyxl',
        '--nofollow-import-to=numba,llvmlite',
        '--nofollow-import-to=pyqtgraph,OpenGL',
        '--nofollow-import-to=numpy',      # project uses no numpy at all

        # Exclude unused Qt sub-modules (not imported by app or qfluentwidgets)
        '--nofollow-import-to=PyQt5.Qt3DAnimation',
        '--nofollow-import-to=PyQt5.Qt3DCore',
        '--nofollow-import-to=PyQt5.Qt3DExtras',
        '--nofollow-import-to=PyQt5.Qt3DInput',
        '--nofollow-import-to=PyQt5.Qt3DLogic',
        '--nofollow-import-to=PyQt5.Qt3DRender',
        '--nofollow-import-to=PyQt5.QtBluetooth',
        '--nofollow-import-to=PyQt5.QtDesigner',
        '--nofollow-import-to=PyQt5.QtHelp',
        '--nofollow-import-to=PyQt5.QtLocation',
        '--nofollow-import-to=PyQt5.QtMultimedia',
        '--nofollow-import-to=PyQt5.QtMultimediaWidgets',
        '--nofollow-import-to=PyQt5.QtNfc',
        '--nofollow-import-to=PyQt5.QtPositioning',
        '--nofollow-import-to=PyQt5.QtQml',
        '--nofollow-import-to=PyQt5.QtQuick',
        '--nofollow-import-to=PyQt5.QtQuick3D',
        '--nofollow-import-to=PyQt5.QtRemoteObjects',
        '--nofollow-import-to=PyQt5.QtSensors',
        '--nofollow-import-to=PyQt5.QtSerialPort',
        '--nofollow-import-to=PyQt5.QtSql',
        '--nofollow-import-to=PyQt5.QtTest',
        '--nofollow-import-to=PyQt5.QtTextToSpeech',
        '--nofollow-import-to=PyQt5.QtWebChannel',
        '--nofollow-import-to=PyQt5.QtWebEngine',
        '--nofollow-import-to=PyQt5.QtWebEngineCore',
        '--nofollow-import-to=PyQt5.QtWebEngineWidgets',
        '--nofollow-import-to=PyQt5.QtWebSockets',
        '--nofollow-import-to=PyQt5.QtXmlPatterns',

        # Wildcard: exclude all test submodules in any package
        '--nofollow-import-to=*.tests',
        '--nofollow-import-to=*.test',
        '--nofollow-import-to=*.testing',

        # ── Required packages ─────────────────────────────────
        # qfluentwidgets ships Python resource files (icons, QSS) — include all
        '--include-package=qfluentwidgets',
        '--include-package-data=qfluentwidgets',
        # qframelesswindow is a hard dependency of qfluentwidgets (FluentWindow)
        # Missing this package is the most common cause of startup failure
        '--include-package=qframelesswindow',
        '--include-package=qframelesswindow.titlebar',
        '--include-package-data=qframelesswindow',
        # python-can loads the PCAN backend dynamically; include the whole package
        '--include-package=can',

        # ── Data files bundled into the package ───────────────
        # CAN hardware driver DLL
        f'--include-data-files={SCRIPT_DIR / "ControlCAN.dll"}=ControlCAN.dll',
        # Window icon and other images
        f'--include-data-dir={SCRIPT_DIR / "img"}=img',
        # Avatar image
        f'--include-data-dir={SCRIPT_DIR / "resource"}=resource',

        # Output exe filename
        f'--output-filename={exe_name}',
    ]

    # Application icon
    icon = SCRIPT_DIR / 'img' / 'star.ico'
    if icon.exists():
        cmd.append(f'--windows-icon-from-ico={icon}')
        log('INFO', f'Icon: {icon.relative_to(SCRIPT_DIR)}')
    else:
        log('WARN', f'Icon not found: {icon.relative_to(SCRIPT_DIR)}')

    cmd.append('--onefile' if mode == 'onefile' else '--standalone')
    cmd.append(str(MAIN_SCRIPT))

    log('INFO', 'Starting Nuitka compilation...')
    log('INFO', '(First run downloads MinGW and compiles C — incremental builds are faster)')
    print()

    result = subprocess.run(cmd)
    if result.returncode != 0:
        print()
        log('ERROR', 'Compilation FAILED!')
        sys.exit(1)

    print()
    log('INFO', 'Compilation succeeded.')

    # ── Copy artifacts to release ─────────────────────────────
    log('INFO', 'Copying artifacts to release directory...')

    if mode == 'onefile':
        src = BUILD_CACHE / exe_name
        if not src.exists():
            log('ERROR', f'Expected output not found: {src}')
            for f in BUILD_CACHE.iterdir():
                print(f'         {f.name}')
            sys.exit(1)

        dst = release_dir / exe_name
        shutil.copy2(src, dst)
        log('INFO', f'Copied exe  -> {dst}')

        # Config and data (user must place DLL next to exe in onefile mode)
        for cfg in CONFIG_FILES:
            src_cfg = SCRIPT_DIR / cfg
            if src_cfg.exists():
                shutil.copy2(src_cfg, release_dir / cfg)
                log('INFO', f'Copied {cfg}')
        for dll in DATA_FILES:
            src_dll = SCRIPT_DIR / dll
            if src_dll.exists():
                shutil.copy2(src_dll, release_dir / dll)
                log('INFO', f'Copied {dll}  (must be in same dir as exe)')

        sign_exe(dst)
        sz = dst.stat().st_size
        print()
        log('INFO', f'Output : {dst.name}')
        log('INFO', f'Size   : {sz // 1_048_576} MB  ({sz // 1024:,} KB)')

    else:  # folder / standalone
        src_dist = BUILD_CACHE / 'main.dist'
        if not src_dist.exists():
            log('ERROR', f'Dist folder not found: {src_dist}')
            for f in BUILD_CACHE.iterdir():
                print(f'         {f.name}')
            sys.exit(1)

        dst_folder = release_dir / folder_name
        if dst_folder.exists():
            log('INFO', f'Removing previous build: {dst_folder.name}')
            shutil.rmtree(dst_folder)

        shutil.copytree(src_dist, dst_folder)
        log('INFO', f'Copied dist -> {dst_folder}')

        # Copy config and extra data files into the dist folder
        for cfg in CONFIG_FILES:
            src_cfg = SCRIPT_DIR / cfg
            if src_cfg.exists():
                shutil.copy2(src_cfg, dst_folder / cfg)
                log('INFO', f'Copied {cfg}')

        # ControlCAN.dll is already bundled via --include-data-files
        # but copy a spare alongside the exe just in case the DLL registers itself
        for dll in DATA_FILES:
            src_dll = SCRIPT_DIR / dll
            if src_dll.exists():
                shutil.copy2(src_dll, dst_folder / dll)
                log('INFO', f'Verified {dll} in dist folder')

        main_exe = dst_folder / exe_name
        sign_exe(main_exe)

        total = sum(f.stat().st_size for f in dst_folder.rglob('*') if f.is_file())
        print()
        log('INFO', f'Output : {dst_folder}')
        log('INFO', f'Size   : {total // 1_048_576} MB  ({total // 1024:,} KB)')

    print()
    print('=' * 60)
    print(f'  Build Complete!  [{mode}]  v{version}')
    print(f'  {release_dir}')
    print('=' * 60)


# ── Entry point ───────────────────────────────────────────────

def main():
    # Default to folder mode — DLL loaded via cwd-relative path
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else 'folder'
    if mode not in ('onefile', 'folder'):
        print(f'[ERROR] Invalid mode: "{mode}"')
        print('        Usage: python build.py [folder|onefile]')
        sys.exit(1)

    os.chdir(SCRIPT_DIR)
    ensure_nuitka()
    build(mode)


if __name__ == '__main__':
    main()
