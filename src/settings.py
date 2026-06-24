"""设置持久化"""
import json
from pathlib import Path
from dataclasses import dataclass, asdict, field

CONFIG_FILE = Path.home() / '.exam_generator' / 'config.json'

@dataclass
class AppSettings:
    provider: str = 'deepseek'
    api_key: str = ''
    api_keys: list = field(default_factory=list)
    poll_strategy: str = 'round_robin'
    model: str = ''
    base_url: str = ''
    temperature: float = 0.7
    max_tokens: int = 8000
    output_dir: str = str(Path.home() / 'Desktop' / '试卷输出')
    knowledge_dir: str = ''
    last_question_types: str = ''
    last_info_fields: str = ''
    last_exam_title: str = '综合知识测试'
    last_exam_subtitle: str = ''
    last_subject: str = ''
    last_exam_time: int = 120
    last_paper_count: int = 1
    last_paper_size: str = 'A3'
    last_difficulty: str = '中等'

    def save(self):
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls) -> 'AppSettings':
        if not CONFIG_FILE.exists(): return cls()
        try:
            with open(CONFIG_FILE, encoding='utf-8') as f:
                data = json.load(f)
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        except Exception: return cls()
