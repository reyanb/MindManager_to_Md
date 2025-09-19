# Mindmap to Markdown for Windows

This folder contains helper scripts to build a Windows `.exe` for the MindManager → Markdown converter.

## Prerequisites

1. Install **Python 3.10+** from [python.org](https://www.python.org/downloads/windows/) and make sure `python` is available in *PATH*.
2. Install dependencies:
   ```powershell
   python -m pip install -r requirements.txt
   ```

## Build the executable

From a PowerShell or Command Prompt window inside this project run:

```powershell
windows_app\build_exe.bat
```

The script calls PyInstaller through `build_exe.py` and produces a self-contained folder at `windows_app\dist\MindmapToMarkdown`. Share that entire folder; no extra installs are required on the target machine. Drag-and-drop support is bundled automatically through `tkinterdnd2`.

## Using the executable

1. Double-click `windows_app\dist\MindmapToMarkdown\MindmapToMarkdown.exe`.
2. Use the GUI to drag/drop a `.mmap` / `.xmmap` file or click **Choose Mind Map…**.
3. When prompted, pick the destination for the Markdown export.

> **Tip**: Install the optional `tkinterdnd2` package to enable drag-and-drop inside the window.

## Regenerating after code changes

Whenever `mindmap_to_md.py` or `mindmap_app.py` changes, rerun the build script to refresh the executable.
