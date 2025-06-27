import sys
import subprocess
import threading
import time
import os

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QPlainTextEdit, QFileDialog,
    QToolBar, QMessageBox, QLineEdit, QHBoxLayout, QLabel, QPushButton, QDialog, QCheckBox, QStatusBar
)
from PySide6.QtGui import QFont, QTextCharFormat, QColor, QSyntaxHighlighter, QAction, QTextCursor
from PySide6.QtCore import Qt, QRegularExpression, Signal, QObject, QTimer
from PySide6.QtWidgets import QListWidget, QListWidgetItem


# === Syntax Highlighter avancé batch ===
class BatchHighlighter(QSyntaxHighlighter):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Batch IDE Pro")
        self.resize(1200, 700)

        self.keyword_format = QTextCharFormat()
        self.keyword_format.setForeground(QColor("#569CD6"))
        self.keyword_format.setFontWeight(QFont.Bold)

        self.comment_format = QTextCharFormat()
        self.comment_format.setForeground(QColor("#6A9955"))
        self.comment_format.setFontItalic(True)

        self.string_format = QTextCharFormat()
        self.string_format.setForeground(QColor("#CE9178"))

        keywords = [
            "echo", "set", "if", "else", "goto", "call", "pause", "exit",
            "rem", "for", "in", "do", "start", "cls", "shift", "cd", "md", "rd", "dir"
        ]
        self.rules = [
            (QRegularExpression(rf"\b{kw}\b", QRegularExpression.CaseInsensitiveOption), self.keyword_format)
            for kw in keywords
        ]

        self.comment_pattern = QRegularExpression(r"^\s*(rem|::).*$", QRegularExpression.CaseInsensitiveOption)
        self.string_pattern = QRegularExpression(r'"[^"\n]*"')

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                match = it.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)

        comment_match = self.comment_pattern.match(text)
        if comment_match.hasMatch():
            self.setFormat(comment_match.capturedStart(), comment_match.capturedLength(), self.comment_format)

        it = self.string_pattern.globalMatch(text)
        while it.hasNext():
            match = it.next()
            self.setFormat(match.capturedStart(), match.capturedLength(), self.string_format)

        # === Variables ===
        self.current_file = None
        self.is_modified = False
        self.runner = None
        self.signals = WorkerSignals()
        self.samples_visible = True

        # === UI Principal ===
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout()
        central.setLayout(main_layout)

        # === Liste de scripts exemples à gauche ===
        self.samples_list = QListWidget()
        self.samples_list.setMaximumWidth(280)
        self.samples_list.setFont(QFont("Consolas", 11))
        self.samples_list.addItems([
            "Clear screen (cls)",
            "Pause script",
            "Echo Hello World",
            "Set variable and echo",
            "Simple IF condition",
            "Loop for /L example"
        ])
        self.samples_list.itemClicked.connect(self.insert_sample_code)
        main_layout.addWidget(self.samples_list)

        # === Zone droite (éditeur + console + input) ===
        right_layout = QVBoxLayout()

        # Éditeur
        self.editor = QPlainTextEdit()
        self.editor.setFont(QFont("Consolas", 12))
        self.highlighter = BatchHighlighter(self.editor.document())
        self.editor.textChanged.connect(self.on_text_changed)
        right_layout.addWidget(self.editor, stretch=3)

        # Console
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Consolas", 11))
        self.console.setStyleSheet("background-color:#1e1e1e; color:#d4d4d4;")
        right_layout.addWidget(self.console, stretch=1)

        # Ligne de commande interactive
        self.console_input = QLineEdit()
        self.console_input.setFont(QFont("Consolas", 12))
        self.console_input.setPlaceholderText("Tape ta commande batch ici et appuie sur Entrée...")
        self.console_input.returnPressed.connect(self.execute_console_command)
        right_layout.addWidget(self.console_input)

        main_layout.addLayout(right_layout)

        # === Toolbar ===
        toolbar = QToolBar()
        self.addToolBar(toolbar)

        open_act = QAction("📂 Ouvrir", self)
        open_act.triggered.connect(self.open_file)
        toolbar.addAction(open_act)

        save_act = QAction("💾 Sauvegarder", self)
        save_act.triggered.connect(self.save_file)
        toolbar.addAction(save_act)

        saveas_act = QAction("💾 Sauvegarder sous...", self)
        saveas_act.triggered.connect(self.save_as_file)
        toolbar.addAction(saveas_act)

        toolbar.addSeparator()

        run_act = QAction("▶️ Lancer", self)
        run_act.triggered.connect(self.run_batch)
        toolbar.addAction(run_act)

        stop_act = QAction("⏹️ Stop", self)
        stop_act.triggered.connect(self.stop_batch)
        toolbar.addAction(stop_act)

        toolbar.addSeparator()

        search_act = QAction("🔍 Rechercher", self)
        search_act.triggered.connect(self.open_search_dialog)
        toolbar.addAction(search_act)

        toggle_samples_act = QAction("📁 Exemples", self)
        toggle_samples_act.triggered.connect(self.toggle_samples)
        toolbar.addAction(toggle_samples_act)

        # === Status bar ===
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.update_status("Prêt")

        # === Connexion signaux d’exécution ===
        self.signals.output.connect(self.append_output)
        self.signals.error.connect(self.append_error)
        self.signals.finished.connect(self.execution_finished)

        # === Auto-save toutes les 60 secondes ===
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self.auto_save)
        self.auto_save_timer.start(60000)

    def toggle_samples(self):
        self.samples_visible = not self.samples_visible
        self.samples_list.setVisible(self.samples_visible)

    def highlightBlock(self, text):
        # Keywords
        for pattern, fmt in self.rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                match = it.next()
                start = match.capturedStart()
                length = match.capturedLength()
                self.setFormat(start, length, fmt)

        # Comments
        comment_match = self.comment_pattern.match(text)
        if comment_match.hasMatch():
            start = comment_match.capturedStart()
            length = comment_match.capturedLength()
            self.setFormat(start, length, self.comment_format)

        # Strings
        it = self.string_pattern.globalMatch(text)
        while it.hasNext():
            match = it.next()
            start = match.capturedStart()
            length = match.capturedLength()
            self.setFormat(start, length, self.string_format)

# === Signal pour thread console ===
class WorkerSignals(QObject):
    output = Signal(str)
    error = Signal(str)
    finished = Signal()

# === Thread d’exécution batch sur fichier ===
class BatchRunner(threading.Thread):
    def __init__(self, script_path, signals):
        super().__init__()
        self.script_path = script_path
        self.signals = signals
        self._stop_flag = False

    def run(self):
        try:
            proc = subprocess.Popen(
                [self.script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                text=True,
                encoding="utf-8"
            )
            while True:
                if self._stop_flag:
                    proc.terminate()
                    self.signals.output.emit("\n[INFO] Exécution arrêtée par l’utilisateur.")
                    break
                out_line = proc.stdout.readline()
                if out_line:
                    self.signals.output.emit(out_line.rstrip())
                err_line = proc.stderr.readline()
                if err_line:
                    self.signals.error.emit(err_line.rstrip())
                if out_line == "" and err_line == "" and proc.poll() is not None:
                    break
                time.sleep(0.01)
            self.signals.finished.emit()
        except Exception as e:
            self.signals.error.emit(f"[ERREUR] Exception: {e}")
            self.signals.finished.emit()

    def stop(self):
        self._stop_flag = True

# === Thread d’exécution batch sur commande interactive ===
class InteractiveBatchRunner(threading.Thread):
    def __init__(self, command, signals):
        super().__init__()
        self.command = command
        self.signals = signals

    def run(self):
        try:
            proc = subprocess.Popen(
                self.command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8"
            )
            while True:
                out_line = proc.stdout.readline()
                if out_line:
                    self.signals.output.emit(out_line.rstrip())
                err_line = proc.stderr.readline()
                if err_line:
                    self.signals.error.emit(err_line.rstrip())
                if out_line == "" and err_line == "" and proc.poll() is not None:
                    break
            self.signals.finished.emit()
        except Exception as e:
            self.signals.error.emit(f"[ERREUR] Exception: {e}")
            self.signals.finished.emit()


# === Fenêtre principale IDE ===
class BatchIDE(QMainWindow):
    def __init__(self, document):
        super().__init__(document)
        self.setWindowTitle("Batch IDE Pro")
        self.resize(1000, 700)

        # Variables
        self.current_file = None
        self.is_modified = False
        self.runner = None
        self.signals = WorkerSignals()

        # UI setup
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout()
        central.setLayout(layout)

        # Editeur
        self.editor = QPlainTextEdit()
        self.editor.setFont(QFont("Consolas", 12))
        self.highlighter = BatchHighlighter(self.editor.document())
        self.editor.textChanged.connect(self.on_text_changed)
        right_layout.addWidget(self.editor, stretch=3)

        # Console sortie (read-only)
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Consolas", 11))
        self.console.setStyleSheet("background-color:#1e1e1e; color:#d4d4d4;")
        layout.addWidget(self.console, stretch=1)

        # Input ligne commande interactive batch
        self.console_input = QLineEdit()
        self.console_input.setFont(QFont("Consolas", 12))
        self.console_input.setPlaceholderText("Tape ta commande batch ici et appuie sur Entrée...")
        layout.addWidget(self.console_input)

        # Toolbar
        toolbar = QToolBar()
        self.addToolBar(toolbar)

        open_act = QAction("📂 Ouvrir", self)
        open_act.triggered.connect(self.open_file)
        toolbar.addAction(open_act)

        save_act = QAction("💾 Sauvegarder", self)
        save_act.triggered.connect(self.save_file)
        toolbar.addAction(save_act)

        saveas_act = QAction("💾 Sauvegarder sous...", self)
        saveas_act.triggered.connect(self.save_as_file)
        toolbar.addAction(saveas_act)

        toolbar.addSeparator()

        run_act = QAction("▶️ Lancer", self)
        run_act.triggered.connect(self.run_batch)
        toolbar.addAction(run_act)

        stop_act = QAction("⏹️ Stop", self)
        stop_act.triggered.connect(self.stop_batch)
        toolbar.addAction(stop_act)

        toolbar.addSeparator()

        search_act = QAction("🔍 Rechercher", self)
        search_act.triggered.connect(self.open_search_dialog)
        toolbar.addAction(search_act)

        # Status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.update_status("Prêt")

        # Connect signals
        self.signals.output.connect(self.append_output)
        self.signals.error.connect(self.append_error)
        self.signals.finished.connect(self.execution_finished)

        # Auto-save timer
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self.auto_save)
        self.auto_save_timer.start(60000)  # toutes les 60 secondes

        # Input commande batch live
        self.console_input.returnPressed.connect(self.execute_interactive_command)
        self.interactive_runner = None

    def update_status(self, message):
        filename = self.current_file if self.current_file else "Sans nom"
        modif = " (modifié)" if self.is_modified else ""
        self.status.showMessage(f"{filename}{modif} — {message}")

    def on_text_changed(self):
        if not self.is_modified:
            self.is_modified = True
            self.update_status("Modifié")

    def open_file(self):
        if self.is_modified:
            if not self.ask_save_changes():
                return

        path, _ = QFileDialog.getOpenFileName(self, "Ouvrir un script batch", filter="Batch Files (*.bat *.cmd);;Tous les fichiers (*.*)")
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
                self.editor.setPlainText(text)
                self.current_file = path
                self.is_modified = False
                self.update_status("Fichier chargé")
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Impossible d’ouvrir le fichier:\n{e}")

    def save_file(self):
        if self.current_file is None:
            self.save_as_file()
            return
        try:
            with open(self.current_file, "w", encoding="utf-8") as f:
                f.write(self.editor.toPlainText())
            self.is_modified = False
            self.update_status("Fichier sauvegardé")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible de sauvegarder le fichier:\n{e}")

    def save_as_file(self):
        path, _ = QFileDialog.getSaveFileName(self, "Sauvegarder sous", filter="Batch Files (*.bat *.cmd);;Tous les fichiers (*.*)")
        if path:
            self.current_file = path
            self.save_file()

    def ask_save_changes(self):
        res = QMessageBox.question(self, "Enregistrer les modifications ?", "Le fichier a été modifié. Voulez-vous sauvegarder ?", QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
        if res == QMessageBox.Yes:
            self.save_file()
            return True
        if res == QMessageBox.No:
            return True
        return False

    def append_output(self, text):
        self.console.setTextColor(QColor("#00ff00"))
        self.console.appendPlainText(text)
        self.console.moveCursor(QTextCursor.End)

    def append_error(self, text):
        self.console.setTextColor(QColor("#ff5555"))
        self.console.appendPlainText(text)
        self.console.moveCursor(QTextCursor.End)

    def execution_finished(self):
        self.update_status("Exécution terminée")
        self.runner = None
        self.interactive_runner = None

    def run_batch(self):
        if self.runner is not None:
            QMessageBox.warning(self, "Attention", "Un script est déjà en cours d'exécution.")
            return

        code = self.editor.toPlainText().strip()
        if not code:
            QMessageBox.warning(self, "Attention", "Le script batch est vide.")
            return

        if self.current_file is None:
            # Sauvegarde dans un fichier temporaire dans dossier de l’app
            tmp_path = os.path.join(os.path.expanduser("~"), "temp_run.bat")
            self.current_file = tmp_path

        self.save_file()

        self.console.clear()
        self.update_status("Exécution en cours...")
        self.runner = BatchRunner(self.current_file, self.signals)
        self.runner.start()

    def stop_batch(self):
        if self.runner is None and self.interactive_runner is None:
            QMessageBox.information(self, "Info", "Aucun script en cours d'exécution.")
            return
        if self.runner:
            self.runner.stop()
            self.runner = None
        if self.interactive_runner:
            # Impossible d’arrêter proprement subprocess shell dans ce mode, on ignore
            self.interactive_runner = None
        self.update_status("Exécution arrêtée")

    def open_search_dialog(self):
        dialog = SearchReplaceDialog(self.editor, self)
        dialog.show()

    def auto_save(self):
        if self.is_modified and self.current_file:
            self.save_file()
            self.update_status("Auto-sauvegarde effectuée")

    def execute_interactive_command(self):
        cmd = self.console_input.text().strip()
        if not cmd:
            return
        self.append_output(f"> {cmd}")
        self.console_input.clear()

        if self.interactive_runner is not None:
            QMessageBox.warning(self, "Attention", "Une commande est déjà en cours d'exécution.")
            return

        self.interactive_runner = InteractiveBatchRunner(cmd, self.signals)
        self.interactive_runner.start()


# === Fenêtre Recherche / Remplacement ===
class SearchReplaceDialog(QDialog):
    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Rechercher / Remplacer")
        self.editor = editor
        self.resize(400, 120)

        layout = QVBoxLayout()
        self.setLayout(layout)

        hlayout1 = QHBoxLayout()
        layout.addLayout(hlayout1)
        hlayout1.addWidget(QLabel("Rechercher:"))
        self.search_input = QLineEdit()
        hlayout1.addWidget(self.search_input)

        hlayout2 = QHBoxLayout()
        layout.addLayout(hlayout2)
        hlayout2.addWidget(QLabel("Remplacer par:"))
        self.replace_input = QLineEdit()
        hlayout2.addWidget(self.replace_input)

        hlayout3 = QHBoxLayout()
        layout.addLayout(hlayout3)
        self.case_checkbox = QCheckBox("Respecter la casse")
        hlayout3.addWidget(self.case_checkbox)
        hlayout3.addStretch()

        hlayout4 = QHBoxLayout()
        layout.addLayout(hlayout4)
        btn_search = QPushButton("Rechercher")
        btn_search.clicked.connect(self.search)
        hlayout4.addWidget(btn_search)
        btn_replace = QPushButton("Remplacer")
        btn_replace.clicked.connect(self.replace)
        hlayout4.addWidget(btn_replace)
        btn_replace_all = QPushButton("Tout remplacer")
        btn_replace_all.clicked.connect(self.replace_all)
        hlayout4.addWidget(btn_replace_all)

    def search(self):
        text = self.search_input.text()
        if not text:
            return
        flags = Qt.CaseSensitive if self.case_checkbox.isChecked() else Qt.CaseInsensitive
        cursor = self.editor.textCursor()
        document = self.editor.document()
        pos = cursor.position()
        found = document.find(text, pos, flags)
        if found.isNull():
            # Recherche depuis le début
            found = document.find(text, 0, flags)
            if found.isNull():
                QMessageBox.information(self, "Recherche", "Texte non trouvé.")
                return
        self.editor.setTextCursor(found)

    def replace(self):
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            cursor.insertText(self.replace_input.text())

    def replace_all(self):
        text = self.search_input.text()
        replace_text = self.replace_input.text()
        if not text:
            return
        flags = Qt.CaseSensitive if self.case_checkbox.isChecked() else Qt.CaseInsensitive
        document = self.editor.document()
        cursor = self.editor.textCursor()
        cursor.beginEditBlock()
        pos = 0
        while True:
            found = document.find(text, pos, flags)
            if found.isNull():
                break
            found.insertText(replace_text)
            pos = found.position()
        cursor.endEditBlock()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet("""
        /* Fenêtre principale */
        QMainWindow {
            background-color: #282c34;
            color: #abb2bf;
            font-family: "Source Code Pro", Consolas, monospace;
            font-size: 13px;
        }
        /* Barre d’outils */
        QToolBar {
            background-color: #21252b;
            spacing: 8px;
            padding: 6px 10px;
            border-bottom: 1px solid #3a3f4b;
        }
        QToolButton {
            background-color: transparent;
            border: none;
            color: #61afef;
            padding: 5px 12px;
            font-weight: 600;
            border-radius: 4px;
        }
        QToolButton:hover {
            background-color: #3e4451;
            color: #e5c07b;
        }
        QToolButton:pressed {
            background-color: #528bff;
            color: #282c34;
        }

        /* Editeur */
        QPlainTextEdit {
            background-color: #1e2127;
            color: #abb2bf;
            border: none;
            padding: 12px;
            selection-background-color: #3e4451;
            selection-color: #d7dae0;
            border-radius: 6px;
        }
        QPlainTextEdit:focus {
            border: 1px solid #61afef;
        }

        /* Console (read-only) */
        QPlainTextEdit:read-only {
            background-color: #21252b;
            color: #98c379;
            border: none;
            padding: 12px;
            border-radius: 6px;
            font-weight: 500;
        }

        /* StatusBar */
        QStatusBar {
            background-color: #21252b;
            color: #abb2bf;
            padding: 6px 12px;
            border-top: 1px solid #3a3f4b;
            font-size: 11px;
        }

        /* MessageBox */
        QMessageBox {
            background-color: #282c34;
            color: #abb2bf;
            font-family: "Source Code Pro", Consolas, monospace;
        }
        QMessageBox QPushButton {
            background-color: #3e4451;
            border: none;
            padding: 6px 15px;
            border-radius: 4px;
            color: #abb2bf;
        }
        QMessageBox QPushButton:hover {
            background-color: #61afef;
            color: #282c34;
        }
    """)
    window = BatchIDE()
    window.show()
    sys.exit(app.exec())
