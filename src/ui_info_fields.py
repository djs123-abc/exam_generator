"""
信息栏字段自定义面板
支持任意字段：姓名、单位及职务、所驻镇村、工号、部门……
"""
import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QGroupBox, QFrame, QScrollArea,
    QMessageBox, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from exam_config_schema import InfoField


PRESETS = {
    '政府/乡村（姓名+单位及职务+所驻镇村）': [
        InfoField('姓名', 1, 15),
        InfoField('单位及职务', 2, 20),
        InfoField('所驻镇村', 1, 15),
    ],
    '学校/培训（姓名+单位/学校+班级）': [
        InfoField('姓名', 1, 15),
        InfoField('单位/学校', 2, 20),
        InfoField('班级', 1, 15),
    ],
    '企业（姓名+部门+工号）': [
        InfoField('姓名', 1, 15),
        InfoField('部门', 1, 15),
        InfoField('工号', 1, 12),
    ],
    '医院（姓名+科室+职务）': [
        InfoField('姓名', 1, 15),
        InfoField('科室', 1, 15),
        InfoField('职务', 1, 12),
    ],
    '简洁（姓名+单位）': [
        InfoField('姓名', 1, 20),
        InfoField('单位', 2, 25),
    ],
    '自定义': [],
}


class FieldRow(QWidget):
    deleted = pyqtSignal(object)
    changed = pyqtSignal()

    def __init__(self, field: InfoField, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self); layout.setContentsMargins(0,2,0,2); layout.setSpacing(6)

        layout.addWidget(QLabel('字段名：'))
        self.label_edit = QLineEdit(field.label)
        self.label_edit.setFixedWidth(100)
        self.label_edit.textChanged.connect(self.changed)
        layout.addWidget(self.label_edit)

        layout.addWidget(QLabel('宽度权重：'))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 5); self.width_spin.setValue(field.width)
        self.width_spin.setFixedWidth(55)
        self.width_spin.valueChanged.connect(self.changed)
        layout.addWidget(self.width_spin)

        layout.addWidget(QLabel('横线长度：'))
        self.blank_spin = QSpinBox()
        self.blank_spin.setRange(5, 40); self.blank_spin.setValue(field.blank_len)
        self.blank_spin.setFixedWidth(55)
        self.blank_spin.valueChanged.connect(self.changed)
        layout.addWidget(self.blank_spin)

        del_btn = QPushButton('✕')
        del_btn.setFixedSize(24, 24)
        del_btn.setStyleSheet('color:red; border:none;')
        del_btn.clicked.connect(lambda: self.deleted.emit(self))
        layout.addWidget(del_btn)
        layout.addStretch()

    def get_field(self) -> InfoField:
        return InfoField(
            label=self.label_edit.text().strip() or '字段',
            width=self.width_spin.value(),
            blank_len=self.blank_spin.value(),
        )


class InfoFieldsWidget(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[FieldRow] = []
        self._build()
        # 默认加载政府模板
        self._load_preset(list(PRESETS.values())[0])

    def _build(self):
        outer = QVBoxLayout(self); outer.setSpacing(6)

        grp = QGroupBox('信息栏字段配置（可自定义任意字段名称和宽度）')
        grp.setStyleSheet('QGroupBox{font-weight:bold;}')
        inner = QVBoxLayout(grp); inner.setSpacing(4)

        # 预设选择
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel('快速预设：'))
        from PyQt6.QtWidgets import QComboBox
        self.preset_combo = QComboBox()
        for name in PRESETS:
            self.preset_combo.addItem(name)
        self.preset_combo.setFixedWidth(260)
        apply_btn = QPushButton('应用')
        apply_btn.setFixedWidth(50)
        apply_btn.clicked.connect(self._apply_preset)
        preset_row.addWidget(self.preset_combo)
        preset_row.addWidget(apply_btn)
        preset_row.addStretch()
        inner.addLayout(preset_row)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet('color:#eee;'); inner.addWidget(sep)

        # 表头
        hdr = QHBoxLayout()
        for txt, w in [('字段名称',100),('  宽度权重(1-5)',120),('  横线长度',100),('',0)]:
            lb = QLabel(txt); lb.setStyleSheet('font-size:10px;color:#555;font-weight:bold;')
            if w: lb.setFixedWidth(w)
            hdr.addWidget(lb)
        hdr.addStretch()
        inner.addLayout(hdr)

        # 行容器
        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(0,0,0,0); self.rows_layout.setSpacing(2)
        inner.addWidget(self.rows_container)

        # 添加按钮
        add_btn = QPushButton('＋ 添加字段')
        add_btn.setFixedHeight(28); add_btn.clicked.connect(lambda: self._add_row(InfoField('新字段',1,15)))
        inner.addWidget(add_btn)

        # 预览
        self.preview_lbl = QLabel()
        self.preview_lbl.setStyleSheet('color:#555;font-size:11px;padding:4px;background:#f9f9f9;border:1px solid #eee;border-radius:3px;')
        self.preview_lbl.setWordWrap(True)
        inner.addWidget(self.preview_lbl)

        outer.addWidget(grp)

    def _add_row(self, field: InfoField):
        row = FieldRow(field)
        row.deleted.connect(self._del_row)
        row.changed.connect(self._update_preview)
        self._rows.append(row)
        self.rows_layout.addWidget(row)
        self._update_preview()

    def _del_row(self, row: FieldRow):
        if len(self._rows) <= 1:
            QMessageBox.information(self, '提示', '至少保留一个字段')
            return
        self._rows.remove(row)
        self.rows_layout.removeWidget(row)
        row.deleteLater()
        self._update_preview()

    def _apply_preset(self):
        name = self.preset_combo.currentText()
        fields = PRESETS.get(name, [])
        if fields:
            self._load_preset(fields)

    def _load_preset(self, fields: list[InfoField]):
        for row in self._rows:
            self.rows_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()
        for f in fields:
            self._add_row(f)

    def _update_preview(self):
        parts = []
        for row in self._rows:
            f = row.get_field()
            parts.append(f"{f.label}：{'_'*f.blank_len}")
        self.preview_lbl.setText('预览：' + '    '.join(parts))
        self.changed.emit()

    def get_fields(self) -> list[InfoField]:
        return [r.get_field() for r in self._rows]

    def set_fields(self, fields: list[InfoField]):
        self._load_preset(fields)

    def to_json(self) -> str:
        return json.dumps([f.__dict__ for f in self.get_fields()], ensure_ascii=False)

    def from_json(self, s: str):
        try:
            data = json.loads(s)
            self.set_fields([InfoField(**d) for d in data])
        except Exception: pass
