"""主窗口 - 含重置按钮、超时配置、题数保证提示"""
import os, sys, subprocess
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QLineEdit, QPushButton, QSpinBox, QComboBox,
    QGroupBox, QTextEdit, QProgressBar, QFileDialog,
    QMessageBox, QScrollArea, QTabWidget, QStatusBar,
    QFrame, QCheckBox, QDoubleSpinBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from settings import AppSettings
from ui_settings import AISettingsWidget
from ui_question_types import QuestionTypesWidget
from ui_info_fields import InfoFieldsWidget
from ui_source import SourcePanel
from exam_config_schema import FullExamConfig, ScoreTableConfig
from exam_engine import ExamEngine
from ai_providers import AIProvider
from worker import GenerationWorker

DIFFICULTIES = ['简单', '中等', '困难', '混合']
PAPER_SIZES  = ['A3', 'A4']


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = AppSettings.load()
        self._worker: GenerationWorker = None
        # 共享 engine，保持跨套去重记录；重置按钮清空它
        self._engine: ExamEngine = None
        self.setWindowTitle('智能出卷系统 v2.0')
        self.setMinimumSize(1200, 840)
        self._build_ui()
        self._apply_style()
        self._restore()

    # ══════════════════════════════════════════════════════════
    #  UI 构建
    # ══════════════════════════════════════════════════════════
    def _build_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(0); root.setContentsMargins(0,0,0,0)
        root.addWidget(self._make_title_bar())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(5)

        # ── 左侧 ─────────────────────────────────────────────
        left = QWidget(); left.setMinimumWidth(620)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(10,10,6,10); ll.setSpacing(8)

        tabs = QTabWidget()
        tabs.setStyleSheet(
            'QTabBar::tab{padding:7px 16px;font-size:12px;}'
            'QTabBar::tab:selected{background:#2980b9;color:white;border-radius:3px 3px 0 0;}')

        self.source_panel = SourcePanel()
        self.source_panel.sources_changed.connect(self._on_src)
        tabs.addTab(self.source_panel, '📂 素材来源')

        scroll_qt = QScrollArea(); scroll_qt.setWidgetResizable(True)
        self.qtype_widget = QuestionTypesWidget()
        scroll_qt.setWidget(self.qtype_widget)
        tabs.addTab(scroll_qt, '📋 题型配置')

        scroll_if = QScrollArea(); scroll_if.setWidgetResizable(True)
        self.info_fields_widget = InfoFieldsWidget()
        scroll_if.setWidget(self.info_fields_widget)
        tabs.addTab(scroll_if, '🪪 信息栏')

        scroll_ai = QScrollArea(); scroll_ai.setWidgetResizable(True)
        self.ai_settings = AISettingsWidget(self.settings)
        scroll_ai.setWidget(self.ai_settings)
        tabs.addTab(scroll_ai, '🤖 AI配置')

        ll.addWidget(tabs, 1)
        ll.addWidget(self._make_exam_config())
        ll.addWidget(self._make_advanced())
        ll.addWidget(self._make_action())
        splitter.addWidget(left)

        # ── 右侧日志 ─────────────────────────────────────────
        right = QWidget(); right.setMinimumWidth(380)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(6,10,10,10); rl.setSpacing(6)
        rl.addWidget(self._make_log_panel())
        splitter.addWidget(right)
        splitter.setSizes([700, 420])

        root.addWidget(splitter, 1)
        self.status_bar = QStatusBar(); self.setStatusBar(self.status_bar)
        self.status_bar.showMessage('就绪 — 请先配置AI，然后添加素材开始出卷')

    def _make_title_bar(self):
        bar = QWidget(); bar.setFixedHeight(52); bar.setObjectName('titleBar')
        lay = QHBoxLayout(bar); lay.setContentsMargins(16,0,16,0)
        lay.addWidget(QLabel('智能出卷系统 v2.0',
            styleSheet='color:white;font-size:18px;font-weight:bold;'))
        lay.addWidget(QLabel(
            '  PDF/Word/图片/URL → A3专业试卷  |  12+AI提供商  |  多Key轮询  |  题目数量精确保证',
            styleSheet='color:#bbdefb;font-size:11px;'))
        lay.addStretch()
        return bar

    def _make_exam_config(self):
        grp = QGroupBox('试卷基本设置')
        grp.setStyleSheet('QGroupBox{font-weight:bold;}')
        row = QHBoxLayout(grp); row.setSpacing(14)

        # 列1
        c1 = QVBoxLayout(); c1.setSpacing(5)
        r = QHBoxLayout(); r.addWidget(QLabel('试卷名称：'))
        self.title_edit = QLineEdit('综合知识测试'); r.addWidget(self.title_edit)
        c1.addLayout(r)
        r2 = QHBoxLayout(); r2.addWidget(QLabel('副　　标：'))
        self.subtitle_edit = QLineEdit()
        self.subtitle_edit.setPlaceholderText('如：（2025年9月）'); r2.addWidget(self.subtitle_edit)
        c1.addLayout(r2)
        r3 = QHBoxLayout(); r3.addWidget(QLabel('科　　目：'))
        self.subject_edit = QLineEdit()
        self.subject_edit.setPlaceholderText('如：法律基础 / 综合知识'); r3.addWidget(self.subject_edit)
        c1.addLayout(r3)
        row.addLayout(c1)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet('color:#ddd;'); row.addWidget(sep)

        # 列2
        c2 = QVBoxLayout(); c2.setSpacing(5)
        r4 = QHBoxLayout(); r4.addWidget(QLabel('考试时间：'))
        self.time_spin = QSpinBox()
        self.time_spin.setRange(10, 300); self.time_spin.setValue(90)
        self.time_spin.setSuffix(' 分钟'); self.time_spin.setFixedWidth(95)
        r4.addWidget(self.time_spin); r4.addStretch(); c2.addLayout(r4)

        r5 = QHBoxLayout(); r5.addWidget(QLabel('出卷套数：'))
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 99); self.count_spin.setValue(1)
        self.count_spin.setSuffix(' 套'); self.count_spin.setFixedWidth(80)
        r5.addWidget(self.count_spin); r5.addStretch(); c2.addLayout(r5)

        r6 = QHBoxLayout(); r6.addWidget(QLabel('难度等级：'))
        self.diff_combo = QComboBox(); self.diff_combo.addItems(DIFFICULTIES)
        self.diff_combo.setCurrentIndex(1); self.diff_combo.setFixedWidth(80)
        r6.addWidget(self.diff_combo); r6.addStretch(); c2.addLayout(r6)
        row.addLayout(c2)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setStyleSheet('color:#ddd;'); row.addWidget(sep2)

        # 列3
        c3 = QVBoxLayout(); c3.setSpacing(5)
        r7 = QHBoxLayout(); r7.addWidget(QLabel('纸张大小：'))
        self.size_combo = QComboBox(); self.size_combo.addItems(PAPER_SIZES)
        self.size_combo.setFixedWidth(70)
        r7.addWidget(self.size_combo); r7.addStretch(); c3.addLayout(r7)

        self.show_score_cb = QCheckBox('每题显示分值')
        self.show_score_cb.setChecked(True); c3.addWidget(self.show_score_cb)
        self.score_table_cb = QCheckBox('显示得分汇总表')
        self.score_table_cb.setChecked(True); c3.addWidget(self.score_table_cb)

        r8 = QHBoxLayout(); r8.addWidget(QLabel('输出目录：'))
        self.output_edit = QLineEdit(self.settings.output_dir)
        browse = QPushButton('…'); browse.setFixedWidth(28)
        browse.clicked.connect(self._browse_output)
        r8.addWidget(self.output_edit, 1); r8.addWidget(browse); c3.addLayout(r8)
        row.addLayout(c3)
        return grp

    def _make_advanced(self):
        """高级设置：超时、重试、特殊要求"""
        grp = QGroupBox('高级设置')
        grp.setStyleSheet('QGroupBox{font-weight:bold;}')
        lay = QVBoxLayout(grp); lay.setSpacing(5)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel('读取超时：'))
        self.timeout_spin = QDoubleSpinBox()
        self.timeout_spin.setRange(60, 600); self.timeout_spin.setValue(240)
        self.timeout_spin.setSuffix(' 秒'); self.timeout_spin.setFixedWidth(100)
        self.timeout_spin.setToolTip('AI接口读取超时时间，网络慢时适当增大（建议240~360秒）')
        row1.addWidget(self.timeout_spin)

        row1.addSpacing(20)
        row1.addWidget(QLabel('最大重试：'))
        self.retry_spin = QSpinBox()
        self.retry_spin.setRange(1, 10); self.retry_spin.setValue(3)
        self.retry_spin.setSuffix(' 次'); self.retry_spin.setFixedWidth(70)
        self.retry_spin.setToolTip('超时或失败时的最大重试次数')
        row1.addWidget(self.retry_spin)

        row1.addSpacing(20)
        row1.addWidget(QLabel('重试间隔：'))
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(1, 30); self.delay_spin.setValue(3)
        self.delay_spin.setSuffix(' 秒'); self.delay_spin.setFixedWidth(80)
        row1.addWidget(self.delay_spin)
        row1.addStretch()
        lay.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel('特殊要求：'))
        self.extra_edit = QLineEdit()
        self.extra_edit.setPlaceholderText('可选补充说明，如"侧重实务操作"、"增加计算题"等')
        row2.addWidget(self.extra_edit)
        lay.addLayout(row2)
        return grp

    def _make_action(self):
        w = QWidget(); lay = QVBoxLayout(w)
        lay.setContentsMargins(0,0,0,0); lay.setSpacing(6)

        # 进度条
        self.prog = QProgressBar()
        self.prog.setRange(0,100); self.prog.setValue(0)
        self.prog.setFixedHeight(20)
        self.prog.setStyleSheet(
            'QProgressBar{border:1px solid #bbb;border-radius:4px;text-align:center;font-size:11px;}'
            'QProgressBar::chunk{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,'
            'stop:0 #2980b9,stop:1 #27ae60);border-radius:3px;}')
        lay.addWidget(self.prog)

        # 按钮行
        btn_row = QHBoxLayout(); btn_row.setSpacing(8)

        self.gen_btn = QPushButton('🚀 开始出卷')
        self.gen_btn.setFixedHeight(44)
        self.gen_btn.setStyleSheet(
            'QPushButton{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,'
            'stop:0 #1a237e,stop:1 #0288d1);color:white;font-size:15px;'
            'font-weight:bold;border:none;border-radius:6px;}'
            'QPushButton:hover{background:#1565C0;}'
            'QPushButton:disabled{background:#aaa;}')
        self.gen_btn.clicked.connect(self._start)

        self.cancel_btn = QPushButton('⛔ 取消')
        self.cancel_btn.setFixedHeight(44); self.cancel_btn.setFixedWidth(80)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel)

        # ── 重置按钮 ────────────────────────────────────────────────────────
        self.reset_btn = QPushButton('🔄 重置记录')
        self.reset_btn.setFixedHeight(44); self.reset_btn.setFixedWidth(110)
        self.reset_btn.setToolTip(
            '清空已出题记录\n重置后，新出的题目可以与之前套卷重复\n'
            '（不重置则系统会自动避免相同题目）')
        self.reset_btn.setStyleSheet(
            'QPushButton{background:#e67e22;color:white;border:none;border-radius:6px;'
            'font-size:12px;font-weight:bold;}'
            'QPushButton:hover{background:#d35400;}')
        self.reset_btn.clicked.connect(self._reset_used)

        self.open_btn = QPushButton('📂 打开目录')
        self.open_btn.setFixedHeight(44); self.open_btn.setFixedWidth(110)
        self.open_btn.clicked.connect(self._open_dir)

        btn_row.addWidget(self.gen_btn, 1)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.reset_btn)
        btn_row.addWidget(self.open_btn)
        lay.addLayout(btn_row)

        # 状态提示
        self.reset_lbl = QLabel('📌 题目记录：空（首次出卷）')
        self.reset_lbl.setStyleSheet('color:#555;font-size:11px;')
        lay.addWidget(self.reset_lbl)
        return w

    def _make_log_panel(self):
        grp = QGroupBox('运行日志')
        grp.setStyleSheet('QGroupBox{font-weight:bold;}')
        v = QVBoxLayout(grp)
        self.log_text = QTextEdit(); self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(
            'QTextEdit{background:#1e1e2e;color:#cdd6f4;'
            'font-family:Consolas,"Courier New",monospace;font-size:11px;'
            'border:1px solid #444;border-radius:4px;}')
        v.addWidget(self.log_text)
        clr = QPushButton('清空日志'); clr.setFixedHeight(24)
        clr.clicked.connect(self.log_text.clear); v.addWidget(clr)
        return grp

    def _apply_style(self):
        self.setStyleSheet("""
            QMainWindow{background:#f5f5f5;}
            #titleBar{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #1a237e,stop:1 #0288d1);}
            QGroupBox{border:1px solid #d0d0d0;border-radius:6px;margin-top:6px;
                      padding:8px;background:white;}
            QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox{
                border:1px solid #ccc;border-radius:4px;padding:3px 6px;
                font-size:12px;background:white;}
            QLineEdit:focus,QSpinBox:focus,QDoubleSpinBox:focus{border-color:#2980b9;}
            QPushButton{border:1px solid #ccc;border-radius:4px;padding:3px 10px;
                        font-size:12px;background:#f0f0f0;}
            QPushButton:hover{background:#e0e8f0;border-color:#2980b9;}
            QTabWidget::pane{border:1px solid #ddd;background:white;border-radius:4px;}
            QSplitter::handle{background:#ddd;}
        """)

    # ══════════════════════════════════════════════════════════
    #  设置读写
    # ══════════════════════════════════════════════════════════
    def _restore(self):
        s = self.settings
        self.title_edit.setText(s.last_exam_title)
        self.subtitle_edit.setText(s.last_exam_subtitle)
        self.subject_edit.setText(s.last_subject)
        self.time_spin.setValue(s.last_exam_time)
        self.count_spin.setValue(s.last_paper_count)
        self.output_edit.setText(s.output_dir)
        if s.last_paper_size in PAPER_SIZES:
            self.size_combo.setCurrentIndex(PAPER_SIZES.index(s.last_paper_size))
        if s.knowledge_dir:
            self.source_panel.set_dir(s.knowledge_dir)
        if s.last_question_types:
            self.qtype_widget.from_json(s.last_question_types)
        if s.last_info_fields:
            self.info_fields_widget.from_json(s.last_info_fields)

    def _save_settings(self):
        self.ai_settings.save_to_settings()
        s = self.settings
        s.last_exam_title    = self.title_edit.text().strip()
        s.last_exam_subtitle = self.subtitle_edit.text().strip()
        s.last_subject       = self.subject_edit.text().strip()
        s.last_exam_time     = self.time_spin.value()
        s.last_paper_count   = self.count_spin.value()
        s.output_dir         = self.output_edit.text().strip()
        s.last_paper_size    = self.size_combo.currentText()
        s.knowledge_dir      = self.source_panel.get_dir_path()
        s.last_question_types = self.qtype_widget.to_json()
        s.last_info_fields    = self.info_fields_widget.to_json()
        s.save()

    # ══════════════════════════════════════════════════════════
    #  槽函数
    # ══════════════════════════════════════════════════════════
    def _on_src(self):
        self.status_bar.showMessage(
            '已添加素材来源' if self.source_panel.has_sources() else '请添加素材来源')

    def _browse_output(self):
        d = QFileDialog.getExistingDirectory(self, '选择输出目录', self.output_edit.text())
        if d: self.output_edit.setText(d)

    def _open_dir(self):
        d = self.output_edit.text().strip()
        if not d or not os.path.isdir(d):
            QMessageBox.information(self, '提示', '输出目录不存在，请先生成试卷')
            return
        if sys.platform == 'win32':
            os.startfile(d)
        elif sys.platform == 'darwin':
            subprocess.run(['open', d])
        else:
            subprocess.run(['xdg-open', d])

    def _reset_used(self):
        """重置已出题记录"""
        reply = QMessageBox.question(
            self, '重置确认',
            '重置后，系统不再记录已出过的题目，\n'
            '后续出卷可能与之前的试卷出现相同题目。\n\n'
            '确认重置？',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        if self._engine:
            self._engine.reset_used()
        self._engine = None   # 彻底新建，不保留任何状态
        self.reset_lbl.setText('📌 题目记录：已重置（下次出卷不避免重复）')
        self.reset_lbl.setStyleSheet('color:#e67e22;font-size:11px;font-weight:bold;')
        self._log('🔄 题目记录已重置，后续套卷可能出现与之前相同的题目')

    def _update_reset_label(self, paper_count: int):
        """出卷完成后更新记录状态"""
        if self._engine:
            total = sum(len(v) for v in self._engine._used.values())
            self.reset_lbl.setText(
                f'📌 题目记录：已记录 {total} 道题（{paper_count} 套），下次出卷将自动去重')
            self.reset_lbl.setStyleSheet('color:#27ae60;font-size:11px;font-weight:bold;')

    def _start(self):
        # 验证
        ai_cfg = self.ai_settings.get_ai_config()
        if not ai_cfg.api_keys:
            QMessageBox.warning(self, '配置缺失', '请在「AI配置」标签页添加至少一个 API Key')
            return
        if not ai_cfg.model:
            QMessageBox.warning(self, '配置缺失', '请选择或填写模型名称')
            return
        if not self.source_panel.has_sources():
            QMessageBox.warning(self, '素材缺失', '请在「素材来源」添加文件、URL 或目录')
            return
        qtypes = self.qtype_widget.get_configs()
        if not any(q.enabled and q.count > 0 for q in qtypes):
            QMessageBox.warning(self, '题型未配置', '请至少启用一种题型并设置题数')
            return
        out = self.output_edit.text().strip()
        if not out:
            QMessageBox.warning(self, '配置缺失', '请设置输出目录')
            return

        # 注入超时/重试参数到 ai_cfg
        ai_cfg.timeout_read = self.timeout_spin.value()
        ai_cfg.max_retries  = self.retry_spin.value()
        ai_cfg.retry_delay  = self.delay_spin.value()

        exam_cfg = FullExamConfig(
            exam_title=self.title_edit.text().strip() or '综合知识测试',
            exam_subtitle=self.subtitle_edit.text().strip(),
            subject=self.subject_edit.text().strip(),
            exam_time=self.time_spin.value(),
            paper_count=self.count_spin.value(),
            difficulty=self.diff_combo.currentText(),
            extra_instructions=self.extra_edit.text().strip(),
            info_fields=self.info_fields_widget.get_fields(),
            score_table=ScoreTableConfig(enabled=self.score_table_cb.isChecked()),
            question_types=qtypes,
            paper_size=self.size_combo.currentText(),
            layout='double_column',
            show_score_per_question=self.show_score_cb.isChecked(),
        )

        self._save_settings()
        self._set_busy(True)
        self.log_text.clear()

        total_q = sum(qt.count for qt in qtypes if qt.enabled)
        self._log(f'🚀 开始出卷：{exam_cfg.exam_title}  '
                  f'{exam_cfg.paper_count}套 × {total_q}题 = '
                  f'{exam_cfg.paper_count * total_q}题  总分{exam_cfg.get_total_score():.4g}分')
        self._log(f'   超时:{ai_cfg.timeout_read:.0f}s  '
                  f'重试:{ai_cfg.max_retries}次  间隔:{ai_cfg.retry_delay:.0f}s')

        self._worker = GenerationWorker(
            ai_config=ai_cfg,
            exam_config=exam_cfg,
            file_paths=self.source_panel.get_file_paths(),
            urls=self.source_panel.get_urls(),
            dir_path=self.source_panel.get_dir_path(),
            output_dir=out,
            engine=self._engine,   # 传入共享engine，保持去重记录
        )
        self._worker.progress.connect(
            lambda p, m: (self.prog.setValue(p), self.status_bar.showMessage(m)))
        self._worker.log_line.connect(self._log)
        self._worker.finished_ok.connect(self._done_ok)
        self._worker.finished_error.connect(self._done_err)
        self._worker.start()

    def _cancel(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
            self._log('⛔ 已取消')
            self._set_busy(False)
            self.prog.setValue(0)

    def _done_ok(self, results: list):
        # 保存 engine 引用，下次出卷继续去重
        if self._worker and self._worker._engine:
            self._engine = self._worker._engine
        self._set_busy(False)
        self.prog.setValue(100)
        self._update_reset_label(len(results))
        n = len(results)
        msg = (f'✅ 完成！共生成 {n} 套试卷\n\n'
               f'输出目录：{self.output_edit.text()}\n\n'
               f'每套包含独立的【试题卷】和【答案卷】Word文件，可直接打印。\n\n'
               f'💡 再次出卷时系统会自动避免重复题目。\n'
               f'   如需允许重复，请点击「重置记录」按钮。')
        reply = QMessageBox.information(self, '出卷完成', msg,
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Open)
        if reply == QMessageBox.StandardButton.Open:
            self._open_dir()

    def _done_err(self, err: str):
        self._set_busy(False)
        self.prog.setValue(0)
        self._log(f'\n❌ 错误: {err}')
        QMessageBox.critical(self, '出卷失败',
            f'发生错误：\n\n{err}\n\n'
            f'💡 建议：\n'
            f'1. 检查网络连接和代理设置\n'
            f'2. 在高级设置中增大"读取超时"时间\n'
            f'3. 减少每题型题目数量（分批出题）\n'
            f'4. 检查API Key是否有效')

    def _log(self, text: str):
        self.log_text.append(text)
        sb = self.log_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _set_busy(self, busy: bool):
        self.gen_btn.setEnabled(not busy)
        self.cancel_btn.setEnabled(busy)
        self.reset_btn.setEnabled(not busy)
        self.gen_btn.setText('⏳ 出卷中...' if busy else '🚀 开始出卷')

    def closeEvent(self, e):
        self._save_settings()
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(2000)
        e.accept()
