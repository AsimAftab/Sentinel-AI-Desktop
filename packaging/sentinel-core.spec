# PyInstaller spec for the Sentinel Core service (onedir, console-less).
# Build:  uv run --group package pyinstaller packaging/sentinel-core.spec --noconfirm

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("websockets")
    + collect_submodules("langchain_mcp_adapters")
    + [
        "pyttsx3.drivers",
        "pyttsx3.drivers.sapi5",
        "comtypes.stream",
        "win32com.gen_py",
        "speech_recognition",
        "pyaudio",
        "keyring.backends.Windows",
    ]
)

datas = (
    collect_data_files("openwakeword")  # bundled melspectrogram/embedding models
    + collect_data_files("speech_recognition")  # flac binaries
    + collect_data_files("langchain_core")
    + collect_data_files("langgraph")
    + collect_data_files("fastembed")  # model registry json
)

binaries = collect_dynamic_libs("sqlite_vec")  # vec0.dll loadable extension

a = Analysis(
    ["core_entry.py"],
    pathex=[".."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "PyQt5", "IPython", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="sentinel-core",
    console=True,  # console app; Tauri spawns it hidden
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="sentinel-core",
)
