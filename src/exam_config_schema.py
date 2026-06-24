"""
试卷自定义配置 Schema
支持信息栏字段、题型、分值、API多Key轮询等完全自定义
"""
import json
from dataclasses import dataclass, field, asdict
from typing import Optional


# ── 信息栏字段（完全自定义）────────────────────────────────────────────────────
@dataclass
class InfoField:
    label: str        # 显示名称，如"姓名"、"单位及职务"、"所驻镇村"
    width: int = 1    # 相对宽度权重（1=均分，2=两倍宽）
    blank_len: int = 20  # 填写横线长度（下划线数）

    def to_dict(self): return asdict(self)
    @classmethod
    def from_dict(cls, d): return cls(**{k:v for k,v in d.items() if k in cls.__dataclass_fields__})


# ── 得分栏配置 ─────────────────────────────────────────────────────────────────
@dataclass
class ScoreTableConfig:
    enabled: bool = True
    sections: list[str] = field(default_factory=lambda: ['一','二','三','四','总分'])
    # sections 留空则自动根据题型生成

    def to_dict(self): return asdict(self)
    @classmethod
    def from_dict(cls, d):
        obj = cls()
        obj.enabled = d.get('enabled', True)
        obj.sections = d.get('sections', ['一','二','三','四','总分'])
        return obj


# ── 题型配置 ─────────────────────────────────────────────────────────────────
@dataclass
class QuestionTypeConfig:
    type_key: str
    count: int
    score_per: float
    enabled: bool = True
    custom_name: str = ''        # 自定义题型名称，留空用默认
    custom_instruction: str = '' # 自定义题型说明，留空用默认

    def to_dict(self): return asdict(self)
    @classmethod
    def from_dict(cls, d): return cls(**{k:v for k,v in d.items() if k in cls.__dataclass_fields__})


# ── API Key 轮询配置 ──────────────────────────────────────────────────────────
@dataclass
class APIKeyEntry:
    api_key: str
    enabled: bool = True
    label: str = ''   # 备注名，如"Key1"、"主Key"

    def to_dict(self): return asdict(self)
    @classmethod
    def from_dict(cls, d): return cls(**{k:v for k,v in d.items() if k in cls.__dataclass_fields__})


# ── 完整试卷配置 ──────────────────────────────────────────────────────────────
@dataclass
class FullExamConfig:
    # 基本信息
    exam_title: str = '综合知识测试'
    exam_subtitle: str = ''           # 副标题，如"（2025年9月）"
    subject: str = ''
    exam_time: int = 120
    paper_count: int = 1
    difficulty: str = '中等'
    extra_instructions: str = ''

    # 信息栏（支持任意字段）
    info_fields: list[InfoField] = field(default_factory=lambda: [
        InfoField('姓名', 1, 15),
        InfoField('单位/学校', 2, 20),
        InfoField('班级', 1, 15),
    ])

    # 得分表格
    score_table: ScoreTableConfig = field(default_factory=ScoreTableConfig)

    # 题型配置
    question_types: list[QuestionTypeConfig] = field(default_factory=list)

    # 页面布局
    paper_size: str = 'A3'           # A3 / A4
    layout: str = 'double_column'    # double_column / single_column
    show_score_per_question: bool = True   # 每题显示分值

    # 来源模式
    source_mode: str = 'generate'    # generate / extract / mix

    def get_total_score(self) -> float:
        return sum(q.count * q.score_per for q in self.question_types if q.enabled)

    def to_json(self) -> str:
        d = {
            'exam_title': self.exam_title,
            'exam_subtitle': self.exam_subtitle,
            'subject': self.subject,
            'exam_time': self.exam_time,
            'paper_count': self.paper_count,
            'difficulty': self.difficulty,
            'extra_instructions': self.extra_instructions,
            'info_fields': [f.to_dict() for f in self.info_fields],
            'score_table': self.score_table.to_dict(),
            'question_types': [q.to_dict() for q in self.question_types],
            'paper_size': self.paper_size,
            'layout': self.layout,
            'show_score_per_question': self.show_score_per_question,
            'source_mode': self.source_mode,
        }
        return json.dumps(d, ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, s: str) -> 'FullExamConfig':
        try:
            d = json.loads(s)
            obj = cls()
            for k in ('exam_title','exam_subtitle','subject','exam_time','paper_count',
                      'difficulty','extra_instructions','paper_size','layout',
                      'show_score_per_question','source_mode'):
                if k in d: setattr(obj, k, d[k])
            if 'info_fields' in d:
                obj.info_fields = [InfoField.from_dict(f) for f in d['info_fields']]
            if 'score_table' in d:
                obj.score_table = ScoreTableConfig.from_dict(d['score_table'])
            if 'question_types' in d:
                obj.question_types = [QuestionTypeConfig.from_dict(q) for q in d['question_types']]
            return obj
        except Exception:
            return cls()
