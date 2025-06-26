
# Batch IDE Pro

---

## Description

**Batch IDE Pro** is an advanced editor to create, edit, and run Windows batch scripts (.bat, .cmd).  
It simplifies batch scripting with syntax highlighting, integrated console, interactive execution, ready-to-use samples, and more.

---

## Features

- **Editor** with syntax highlighting and basic error detection  
- **Integrated console** showing real-time stdout and stderr output  
- **Safe script execution** with manual stop capability  
- **Interactive mode** to run batch commands live  
- **Built-in samples** to easily learn and insert common scripts  
- **Find & Replace** functionality with case sensitivity support  
- **Auto-save** every 60 seconds to prevent data loss  
- **Modern UI** with dark theme, custom toolbar, and notifications  
- Tracks unsaved changes with visual status bar updates

---

## Installation

---

### Requirements

- Python 3.7 or higher  
- PySide6 (install via pip)

```bash
pip install PySide6
```

## Usage
---

Run the app with:


```python
python main.py
```

## Main commands
---

    - Open an existing batch file

    - Save or Save As your script

    - Run the current batch script

    - Stop running scripts

    - Show / Hide sample scripts panel

    - Find / Replace text in the editor

    - Execute batch commands interactively in the console

## Project structure
---

    - BatchIDE: main class handling the UI

    - BatchHighlighter: advanced batch syntax highlighting

    - BatchRunner and InteractiveBatchRunner: multi-threaded batch execution

    - SearchReplaceDialog: find & replace dialog

    - SampleCodeWidget: sample batch scripts list for insertion

    - Supporting files and resources (icons, styles, etc.)

### License
---

This project is licensed under the MIT License. Feel free to modify, share, and use freely.
Thanks

Thanks to the Python community and all open source contributors.
Made with ❤️ by bowser-2077
