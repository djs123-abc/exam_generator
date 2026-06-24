"""
AI配置面板 - 支持多Key轮询
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QPushButton,
    QSpinBox, QDoubleSpinBox, QGroupBox, QMessageBox,
    QListWidget, QListWidgetItem, QTextEdit, QTabWidget,
    QButtonGroup, QRadioButton
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from ai_providers import PROVIDER_CONFIGS, AIConfig, AIProvider
from settings import AppSettings


class TestThread(QThread):
    result = pyqtSignal(bool, str)
    def __init__(self, config): super().__init__(); self.config = config
    def run(self):
        try:
            p = AIProvider(self.config)
            ok, msg = p.test_connection()
            self.result.emit(ok, msg)
        except Exception as e:
            self.result.emit(False, str(e))


class MultiKeyWidget(QWidget):
    """多Key管理：列表 + 增删"""
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.setSpacing(4)

        top = QHBoxLayout()
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText('输入 API Key 后点击添加...')
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.show_btn = QPushButton('显示')
        self.show_btn.setFixedWidth(44); self.show_btn.setCheckable(True)
        self.show_btn.toggled.connect(lambda c: (
            self.key_input.setEchoMode(QLineEdit.EchoMode.Normal if c else QLineEdit.EchoMode.Password),
            self.show_btn.setText('隐藏' if c else '显示')
        ))
        self.add_btn = QPushButton('＋添加')
        self.add_btn.setFixedWidth(60)
        self.add_btn.clicked.connect(self._add)
        top.addWidget(self.key_input, 1); top.addWidget(self.show_btn); top.addWidget(self.add_btn)
        layout.addLayout(top)

        self.list_widget = QListWidget()
        self.list_widget.setMaximumHeight(100)
        self.list_widget.setStyleSheet('font-family: Consolas, monospace; font-size: 11px;')
        layout.addWidget(self.list_widget)

        btn_row = QHBoxLayout()
        self.del_btn = QPushButton('删除选中')
        self.del_btn.setFixedHeight(24); self.del_btn.clicked.connect(self._delete)
        self.clear_btn = QPushButton('清空')
        self.clear_btn.setFixedHeight(24); self.clear_btn.clicked.connect(self._clear)
        btn_row.addWidget(self.del_btn); btn_row.addWidget(self.clear_btn); btn_row.addStretch()
        layout.addLayout(btn_row)

        lbl = QLabel('多个Key将按轮询策略依次调用，某个Key失败自动切换下一个')
        lbl.setStyleSheet('color:#777; font-size:10px;')
        layout.addWidget(lbl)

    def _add(self):
        key = self.key_input.text().strip()
        if not key: return
        # 检查重复
        for i in range(self.list_widget.count()):
            if self.list_widget.item(i).data(Qt.ItemDataRole.UserRole) == key:
                QMessageBox.information(self, '提示', '该Key已存在')
                return
        idx = self.list_widget.count() + 1
        item = QListWidgetItem(f'Key{idx}: {key[:8]}...{key[-4:]}')
        item.setData(Qt.ItemDataRole.UserRole, key)
        self.list_widget.addItem(item)
        self.key_input.clear()
        self.changed.emit()

    def _delete(self):
        for item in self.list_widget.selectedItems():
            self.list_widget.takeItem(self.list_widget.row(item))
        self.changed.emit()

    def _clear(self):
        self.list_widget.clear(); self.changed.emit()

    def get_keys(self) -> list[str]:
        return [self.list_widget.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.list_widget.count())]

    def set_keys(self, keys: list[str]):
        self.list_widget.clear()
        for i, k in enumerate(keys):
            if not k.strip(): continue
            item = QListWidgetItem(f'Key{i+1}: {k[:8]}...{k[-4:] if len(k)>12 else ""}')
            item.setData(Qt.ItemDataRole.UserRole, k)
            self.list_widget.addItem(item)


class AISettingsWidget(QWidget):
    settings_changed = pyqtSignal()

    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._build()
        self._load()

    def _build(self):
        layout = QVBoxLayout(self); layout.setSpacing(10)

        grp = QGroupBox('AI 大模型配置')
        grp.setStyleSheet('QGroupBox{font-weight:bold;font-size:13px;padding-top:8px;}')
        form = QFormLayout(grp); form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # 提供商
        self.provider_combo = QComboBox()
        for k, v in PROVIDER_CONFIGS.items():
            self.provider_combo.addItem(v['name'], k)
        self.provider_combo.currentIndexChanged.connect(self._on_provider)
        form.addRow('AI 提供商：', self.provider_combo)

        # 模型
        self.model_combo = QComboBox(); self.model_combo.setEditable(True)
        self.model_combo.setPlaceholderText('选择或输入模型名称')
        form.addRow('模型名称：', self.model_combo)

        # 自定义端点
        self.base_url_edit = QLineEdit()
        self.base_url_edit.setPlaceholderText('留空使用默认端点，代理时填写')
        form.addRow('API 端点：', self.base_url_edit)

        # 多Key管理
        self.multi_key = MultiKeyWidget()
        self.multi_key.changed.connect(self.settings_changed)
        form.addRow('API Keys：', self.multi_key)

        # 轮询策略
        strat_row = QHBoxLayout()
        self.strat_rr  = QRadioButton('轮询(Round Robin)')
        self.strat_fb  = QRadioButton('主备(Failover)')
        self.strat_rnd = QRadioButton('随机(Random)')
        self.strat_rr.setChecked(True)
        for rb in (self.strat_rr, self.strat_fb, self.strat_rnd):
            strat_row.addWidget(rb)
        strat_row.addStretch()
        form.addRow('轮询策略：', strat_row)

        # 温度
        t_row = QHBoxLayout()
        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 2.0); self.temp_spin.setSingleStep(0.1)
        self.temp_spin.setValue(0.7); self.temp_spin.setFixedWidth(75)
        self.temp_lbl = QLabel('0.7')
        self.temp_spin.valueChanged.connect(lambda v: self.temp_lbl.setText(f'{v:.1f}'))
        t_row.addWidget(self.temp_spin); t_row.addWidget(self.temp_lbl); t_row.addStretch()
        form.addRow('温　　度：', t_row)

        # max_tokens
        self.tokens_spin = QSpinBox()
        self.tokens_spin.setRange(1000, 32000); self.tokens_spin.setSingleStep(1000)
        self.tokens_spin.setValue(8000); self.tokens_spin.setFixedWidth(90)
        form.addRow('Max Token：', self.tokens_spin)

        layout.addWidget(grp)

        # 测试连接
        test_row = QHBoxLayout()
        self.test_btn = QPushButton('🔗 测试连接')
        self.test_btn.setFixedHeight(34); self.test_btn.clicked.connect(self._test)
        self.test_lbl = QLabel('')
        self.test_lbl.setWordWrap(True)
        test_row.addWidget(self.test_btn); test_row.addWidget(self.test_lbl, 1)
        layout.addLayout(test_row)

        # 各平台链接
        tips = QGroupBox('API Key 获取地址')
        tl = QVBoxLayout(tips)
        tip_text = QLabel(
            '• Anthropic: https://console.anthropic.com\n'
            '• OpenAI: https://platform.openai.com\n'
            '• DeepSeek: https://platform.deepseek.com\n'
            '• 通义千问: https://dashscope.aliyuncs.com\n'
            '• 文心一言: https://cloud.baidu.com\n'
            '• 豆包: https://www.volcengine.com\n'
            '• Kimi: https://platform.moonshot.cn\n'
            '• 智谱GLM: https://open.bigmodel.cn\n'
            '• 讯飞星火: https://xinghuo.xfyun.cn\n'
            '• Gemini: https://aistudio.google.com\n'
            '• Groq: https://console.groq.com'
        )
        tip_text.setStyleSheet('color:#555;font-size:10px;line-height:1.6;')
        tl.addWidget(tip_text)
        layout.addWidget(tips)
        layout.addStretch()

    def _on_provider(self):
        k = self.provider_combo.currentData()
        cfg = PROVIDER_CONFIGS.get(k, {})
        self.model_combo.clear()
        for m in cfg.get('models', []):
            self.model_combo.addItem(m)
        dm = cfg.get('default_model','')
        if dm:
            idx = self.model_combo.findText(dm)
            if idx >= 0: self.model_combo.setCurrentIndex(idx)
        self.base_url_edit.setPlaceholderText(
            f'默认: {cfg.get("base_url","")}  (留空即可)')

    def _test(self):
        cfg = self._get_config()
        if not cfg.api_keys:
            QMessageBox.warning(self, '提示', '请先添加至少一个 API Key')
            return
        self.test_btn.setEnabled(False); self.test_btn.setText('测试中...')
        self._t = TestThread(cfg)
        self._t.result.connect(self._on_test)
        self._t.start()

    def _on_test(self, ok, msg):
        self.test_btn.setEnabled(True); self.test_btn.setText('🔗 测试连接')
        color = '#27ae60' if ok else '#e74c3c'
        self.test_lbl.setText(f'<span style="color:{color}">{msg}</span>')

    def _get_config(self) -> AIConfig:
        strat = ('round_robin' if self.strat_rr.isChecked() else
                 'failover'    if self.strat_fb.isChecked() else 'random')
        return AIConfig(
            provider=self.provider_combo.currentData() or 'custom',
            api_keys=self.multi_key.get_keys(),
            model=self.model_combo.currentText().strip(),
            base_url=self.base_url_edit.text().strip(),
            temperature=self.temp_spin.value(),
            max_tokens=self.tokens_spin.value(),
            poll_strategy=strat,
        )

    def _load(self):
        s = self.settings
        for i in range(self.provider_combo.count()):
            if self.provider_combo.itemData(i) == s.provider:
                self.provider_combo.setCurrentIndex(i); break
        self._on_provider()
        keys = s.api_keys if hasattr(s,'api_keys') and s.api_keys else ([s.api_key] if s.api_key else [])
        self.multi_key.set_keys(keys)
        if s.model:
            idx = self.model_combo.findText(s.model)
            if idx >= 0: self.model_combo.setCurrentIndex(idx)
            else: self.model_combo.setCurrentText(s.model)
        self.base_url_edit.setText(s.base_url)
        self.temp_spin.setValue(s.temperature)
        self.tokens_spin.setValue(s.max_tokens)

    def save_to_settings(self):
        cfg = self._get_config()
        self.settings.provider = cfg.provider
        self.settings.api_keys = cfg.api_keys
        self.settings.api_key  = cfg.api_key
        self.settings.model    = cfg.model
        self.settings.base_url = cfg.base_url
        self.settings.temperature = cfg.temperature
        self.settings.max_tokens  = cfg.max_tokens
        self.settings.poll_strategy = cfg.poll_strategy

    def get_ai_config(self) -> AIConfig:
        return self._get_config()
