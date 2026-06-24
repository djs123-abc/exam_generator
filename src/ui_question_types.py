"""题型配置面板 - 支持自定义名称、说明、分值"""
import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox,
    QDoubleSpinBox, QCheckBox, QGroupBox, QFrame, QLineEdit, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from exam_config_schema import QuestionTypeConfig
from exam_engine import QUESTION_TYPES, DEFAULT_INSTRUCTIONS

TYPE_DEFAULTS = {
    'single_choice': (20, 1.5, True),
    'multi_choice':  (5,  3.0, False),
    'true_false':    (10, 1.5, True),
    'fill_blank':    (20, 1.0, True),
    'short_answer':  (3,  5.0, True),
    'essay':         (1,  10.0, False),
    'case_analysis': (2,  10.0, True),
}

class QTypeRow(QWidget):
    changed = pyqtSignal()
    def __init__(self, type_key, parent=None):
        super().__init__(parent)
        self.type_key = type_key
        dc, ds, de = TYPE_DEFAULTS.get(type_key, (5,2,True))
        layout = QHBoxLayout(self); layout.setContentsMargins(2,2,2,2); layout.setSpacing(6)

        self.cb = QCheckBox(); self.cb.setChecked(de)
        self.cb.toggled.connect(self._toggle)
        layout.addWidget(self.cb)

        default_name = QUESTION_TYPES.get(type_key, type_key)
        self.name_edit = QLineEdit(default_name)
        self.name_edit.setFixedWidth(90); self.name_edit.setPlaceholderText('题型名')
        self.name_edit.textChanged.connect(self.changed)
        layout.addWidget(self.name_edit)

        self.inst_edit = QLineEdit()
        self.inst_edit.setPlaceholderText('题型说明（留空用默认）')
        self.inst_edit.setFixedWidth(200)
        self.inst_edit.textChanged.connect(self.changed)
        layout.addWidget(self.inst_edit)

        layout.addStretch()

        layout.addWidget(QLabel('题数：'))
        self.count_spin = QSpinBox()
        self.count_spin.setRange(0,200); self.count_spin.setValue(dc)
        self.count_spin.setFixedWidth(65)
        self.count_spin.valueChanged.connect(self._update)
        layout.addWidget(self.count_spin)

        layout.addWidget(QLabel('每题：'))
        self.score_spin = QDoubleSpinBox()
        self.score_spin.setRange(0.5,100); self.score_spin.setSingleStep(0.5)
        self.score_spin.setValue(ds); self.score_spin.setFixedWidth(70)
        self.score_spin.valueChanged.connect(self._update)
        layout.addWidget(self.score_spin)
        layout.addWidget(QLabel('分'))

        self.subtotal = QLabel()
        self.subtotal.setFixedWidth(80)
        self.subtotal.setStyleSheet('color:#2980b9;font-weight:bold;')
        layout.addWidget(self.subtotal)
        self._toggle(de); self._update()

    def _toggle(self, checked):
        for w in (self.count_spin, self.score_spin, self.name_edit, self.inst_edit):
            w.setEnabled(checked)
        self._update()

    def _update(self):
        if self.cb.isChecked():
            t = self.count_spin.value() * self.score_spin.value()
            self.subtotal.setText(f'小计{t:.4g}分')
        else:
            self.subtotal.setText('（禁用）')
        self.changed.emit()

    def get_config(self) -> QuestionTypeConfig:
        return QuestionTypeConfig(
            type_key=self.type_key,
            count=self.count_spin.value(),
            score_per=self.score_spin.value(),
            enabled=self.cb.isChecked(),
            custom_name=self.name_edit.text().strip(),
            custom_instruction=self.inst_edit.text().strip(),
        )
    def set_config(self, cfg: QuestionTypeConfig):
        self.cb.setChecked(cfg.enabled)
        self.count_spin.setValue(cfg.count)
        self.score_spin.setValue(cfg.score_per)
        if cfg.custom_name: self.name_edit.setText(cfg.custom_name)
        if cfg.custom_instruction: self.inst_edit.setText(cfg.custom_instruction)


class QuestionTypesWidget(QWidget):
    total_changed = pyqtSignal(float)
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: dict[str, QTypeRow] = {}
        self._build()

    def _build(self):
        outer = QVBoxLayout(self); outer.setSpacing(4)
        grp = QGroupBox('题型与分值配置（支持自定义题型名称和说明）')
        grp.setStyleSheet('QGroupBox{font-weight:bold;}')
        inner = QVBoxLayout(grp); inner.setSpacing(2)

        # 表头
        hdr = QHBoxLayout(); hdr.setContentsMargins(4,0,4,0)
        for txt, w in [('启',20),('题型名称',90),('题型说明（留空用默认）',200),('',0),
                       ('题数',75),('分值',80),('',20),('小计',80)]:
            lb = QLabel(txt)
            lb.setStyleSheet('color:#333;font-size:10px;font-weight:bold;')
            if w: lb.setFixedWidth(w)
            hdr.addWidget(lb)
        hdr.addStretch()
        inner.addLayout(hdr)
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet('color:#ddd;'); inner.addWidget(sep)

        for key in QUESTION_TYPES:
            row = QTypeRow(key)
            row.changed.connect(self._update)
            self._rows[key] = row
            inner.addWidget(row)
            s = QFrame(); s.setFrameShape(QFrame.Shape.HLine)
            s.setStyleSheet('color:#f0f0f0;'); inner.addWidget(s)

        outer.addWidget(grp)
        tr = QHBoxLayout(); tr.addStretch()
        self.total_lbl = QLabel('总分：0分')
        self.total_lbl.setStyleSheet('font-size:16px;font-weight:bold;color:#c0392b;')
        tr.addWidget(self.total_lbl); outer.addLayout(tr)
        self._update()

    def _update(self):
        t = sum(r.get_config().count * r.get_config().score_per
                for r in self._rows.values() if r.get_config().enabled)
        self.total_lbl.setText(f'总分：{t:.4g}分')
        self.total_changed.emit(t)

    def get_configs(self) -> list[QuestionTypeConfig]:
        return [r.get_config() for r in self._rows.values()]

    def set_configs(self, cfgs: list[QuestionTypeConfig]):
        for c in cfgs:
            if c.type_key in self._rows:
                self._rows[c.type_key].set_config(c)

    def to_json(self) -> str:
        return json.dumps([c.__dict__ for c in self.get_configs()], ensure_ascii=False)

    def from_json(self, s: str):
        try:
            data = json.loads(s)
            self.set_configs([QuestionTypeConfig(**d) for d in data])
        except Exception: pass
