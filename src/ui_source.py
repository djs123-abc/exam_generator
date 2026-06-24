"""
素材来源面板 - 文件上传 / URL / 指定目录
"""
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QLineEdit, QPushButton, QListWidget, QListWidgetItem,
    QFileDialog, QGroupBox, QTextEdit, QMessageBox,
    QProgressBar, QSizePolicy, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QMimeData
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QIcon

SUPPORTED_FILTERS = (
    "支持的文件 (*.pdf *.docx *.doc *.xlsx *.xls *.csv *.pptx *.ppt "
    "*.txt *.md *.jpg *.jpeg *.png *.bmp *.tiff *.webp);;"
    "PDF文件 (*.pdf);;"
    "Word文档 (*.docx *.doc);;"
    "图片文件 (*.jpg *.jpeg *.png *.bmp *.tiff *.webp);;"
    "所有文件 (*)"
)


class SourcePanel(QWidget):
    sources_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._file_paths: list[str] = []
        self._urls: list[str] = []
        self._dir_path: str = ""
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #ddd; border-radius: 4px; }
            QTabBar::tab { padding: 6px 16px; font-size: 12px; }
            QTabBar::tab:selected { background: #2980b9; color: white; border-radius: 3px; }
        """)

        # ── Tab1: 上传文件 ──
        file_tab = QWidget()
        ft_layout = QVBoxLayout(file_tab)

        btn_row = QHBoxLayout()
        self.add_files_btn = QPushButton("＋ 添加文件")
        self.add_files_btn.clicked.connect(self._add_files)
        self.add_files_btn.setFixedHeight(32)
        self.clear_files_btn = QPushButton("清空")
        self.clear_files_btn.clicked.connect(self._clear_files)
        self.clear_files_btn.setFixedHeight(32)
        self.clear_files_btn.setFixedWidth(60)
        btn_row.addWidget(self.add_files_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.clear_files_btn)
        ft_layout.addLayout(btn_row)

        self.file_list = QListWidget()
        self.file_list.setAcceptDrops(True)
        self.file_list.setMinimumHeight(140)
        self.file_list.setStyleSheet("font-size: 11px;")
        # 删除选中
        self.file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        ft_layout.addWidget(self.file_list)

        remove_btn = QPushButton("删除选中")
        remove_btn.clicked.connect(self._remove_selected_files)
        remove_btn.setFixedHeight(28)
        ft_layout.addWidget(remove_btn)

        tip = QLabel("支持：PDF、Word、Excel、PPT、图片(OCR)、TXT\n可直接拖拽文件到列表")
        tip.setStyleSheet("color: #888; font-size: 10px;")
        ft_layout.addWidget(tip)
        tabs.addTab(file_tab, "📄 上传文件")

        # ── Tab2: URL链接 ──
        url_tab = QWidget()
        ul_layout = QVBoxLayout(url_tab)
        ul_layout.addWidget(QLabel("每行一个URL，支持网页抓取："))
        self.url_edit = QTextEdit()
        self.url_edit.setPlaceholderText(
            "https://example.com/article\nhttps://example.com/page2\n..."
        )
        self.url_edit.setMinimumHeight(160)
        self.url_edit.textChanged.connect(self.sources_changed)
        ul_layout.addWidget(self.url_edit)
        tip2 = QLabel("自动抓取网页正文内容，过滤广告和导航")
        tip2.setStyleSheet("color: #888; font-size: 10px;")
        ul_layout.addWidget(tip2)
        tabs.addTab(url_tab, "🌐 URL链接")

        # ── Tab3: 指定目录 ──
        dir_tab = QWidget()
        dl_layout = QVBoxLayout(dir_tab)
        dir_row = QHBoxLayout()
        self.dir_edit = QLineEdit()
        self.dir_edit.setPlaceholderText("选择包含知识材料的文件夹")
        self.dir_edit.textChanged.connect(self._on_dir_changed)
        dir_btn = QPushButton("浏览…")
        dir_btn.clicked.connect(self._browse_dir)
        dir_btn.setFixedWidth(60)
        dir_row.addWidget(self.dir_edit)
        dir_row.addWidget(dir_btn)
        dl_layout.addLayout(dir_row)

        self.dir_file_list = QListWidget()
        self.dir_file_list.setMinimumHeight(140)
        self.dir_file_list.setStyleSheet("font-size: 11px;")
        dl_layout.addWidget(self.dir_file_list)

        self.dir_status = QLabel("尚未选择目录")
        self.dir_status.setStyleSheet("color: #888; font-size: 11px;")
        dl_layout.addWidget(self.dir_status)
        tabs.addTab(dir_tab, "📁 指定目录")

        layout.addWidget(tabs)
        self._tabs = tabs

        # 拖拽支持
        self.setAcceptDrops(True)

    # ── 文件操作 ──────────────────────────────────────────────────────────────
    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择知识材料文件", "", SUPPORTED_FILTERS
        )
        for p in paths:
            if p not in self._file_paths:
                self._file_paths.append(p)
                item = QListWidgetItem(f"📄 {Path(p).name}")
                item.setToolTip(p)
                self.file_list.addItem(item)
        if paths:
            self.sources_changed.emit()

    def _remove_selected_files(self):
        for item in self.file_list.selectedItems():
            row = self.file_list.row(item)
            self.file_list.takeItem(row)
            if row < len(self._file_paths):
                self._file_paths.pop(row)
        self.sources_changed.emit()

    def _clear_files(self):
        self._file_paths.clear()
        self.file_list.clear()
        self.sources_changed.emit()

    # ── 目录操作 ──────────────────────────────────────────────────────────────
    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择知识材料目录", "")
        if d:
            self.dir_edit.setText(d)

    def _on_dir_changed(self, path):
        self._dir_path = path
        self.dir_file_list.clear()
        if path and os.path.isdir(path):
            exts = {'.pdf','.docx','.doc','.xlsx','.xls','.csv',
                    '.pptx','.ppt','.txt','.md',
                    '.jpg','.jpeg','.png','.bmp','.tiff','.webp'}
            count = 0
            for root, dirs, files in os.walk(path):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for fn in files:
                    if Path(fn).suffix.lower() in exts:
                        rel = os.path.relpath(os.path.join(root, fn), path)
                        self.dir_file_list.addItem(f"📄 {rel}")
                        count += 1
            self.dir_status.setText(f"共找到 {count} 个文件")
        else:
            self.dir_status.setText("目录不存在")
        self.sources_changed.emit()

    # ── 拖拽 ──────────────────────────────────────────────────────────────────
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            p = url.toLocalFile()
            if os.path.isfile(p) and p not in self._file_paths:
                self._file_paths.append(p)
                item = QListWidgetItem(f"📄 {Path(p).name}")
                item.setToolTip(p)
                self.file_list.addItem(item)
        self._tabs.setCurrentIndex(0)
        self.sources_changed.emit()

    # ── 对外接口 ──────────────────────────────────────────────────────────────
    def get_file_paths(self) -> list[str]:
        return list(self._file_paths)

    def get_urls(self) -> list[str]:
        raw = self.url_edit.toPlainText().strip()
        if not raw:
            return []
        return [u.strip() for u in raw.splitlines() if u.strip().startswith("http")]

    def get_dir_path(self) -> str:
        return self._dir_path

    def has_sources(self) -> bool:
        return bool(self._file_paths or self.get_urls() or self._dir_path)

    def set_dir(self, path: str):
        if path:
            self.dir_edit.setText(path)
            self._tabs.setCurrentIndex(2)
