"""
出卷引擎
- 题目数量严格保证：分批出题 + 补全机制
- 支持重置（清空已出题记录）
- 单次Prompt按题型拆分，避免数量不足
"""
import json, re, logging
from dataclasses import dataclass, field
from exam_config_schema import FullExamConfig, QuestionTypeConfig

logger = logging.getLogger(__name__)

QUESTION_TYPES = {
    "single_choice": "单项选择题",
    "multi_choice":  "多项选择题",
    "true_false":    "判断题",
    "fill_blank":    "填空题",
    "short_answer":  "简答题",
    "essay":         "论述题",
    "case_analysis": "案例分析题",
}

DEFAULT_INSTRUCTIONS = {
    "single_choice": "（每题只有一个正确答案，请将正确选项字母填入括号内）",
    "multi_choice":  "（每题有两个或两个以上正确答案，全对得满分，漏选得一半分，错选不得分）",
    "true_false":    "（请判断下列说法正误，正确填√，错误填×）",
    "fill_blank":    "（请在横线上填写正确答案）",
    "short_answer":  "（请简明扼要地回答下列问题）",
    "essay":         "（请结合所学知识进行系统阐述）",
    "case_analysis": "（请认真阅读案例，分析并回答问题）",
}

TYPE_ORDER = ["single_choice","multi_choice","true_false",
              "fill_blank","short_answer","essay","case_analysis"]

# 每次请求最多生成的题目数（避免单次过多导致超时/截断）
MAX_PER_BATCH = 15

SYSTEM_PROMPT = """你是一位专业的教育考试命题专家，根据提供的知识材料精准出题。
严格按JSON格式输出，不包含任何markdown代码块标记（```json 或 ```）。
所有题目必须基于材料内容。判断题答案要正确与错误均有，不能全是正确。
输出题目数量必须与要求完全一致，不能多也不能少。"""


@dataclass
class Question:
    q_type: str
    number: int
    content: str
    options: list = field(default_factory=list)
    answer: str = ""
    analysis: str = ""
    score: float = 0


@dataclass
class ExamPaper:
    paper_index: int
    title: str
    config: FullExamConfig
    questions: list = field(default_factory=list)


# ── Prompt 构建（单题型，精确数量控制）────────────────────────────────────────
def _build_batch_prompt(knowledge: str, qt_cfg: QuestionTypeConfig,
                        need_count: int, paper_idx: int,
                        used_contents: list, config: FullExamConfig) -> str:
    """为单个题型构建精确 Prompt"""
    type_name = qt_cfg.custom_name or QUESTION_TYPES.get(qt_cfg.type_key, qt_cfg.type_key)
    score_per  = qt_cfg.score_per
    diff       = config.difficulty

    avoid_hint = ""
    if used_contents:
        samples = used_contents[-10:]  # 只参考最近10条
        avoid_hint = "\n【避免重复以下已出题目】\n" + "\n".join(f"- {s}" for s in samples)

    # 根据题型给出具体的JSON示例
    example = _get_example(qt_cfg.type_key, score_per)

    return f"""请根据以下知识材料，出{need_count}道【{type_name}】，每题{score_per}分，难度【{diff}】。

【知识材料】
{knowledge[:5000]}

{avoid_hint}

【要求】
1. 必须严格出{need_count}道题，不能多也不能少
2. 题目必须基于材料内容，不得脱离材料
3. 选择题选项必须是4个（A/B/C/D），答案明确
4. 判断题答案正确和错误都要有，不能全对或全错
5. 案例分析题必须包含案例背景和具体问题

【JSON格式】直接输出JSON，不要任何说明文字和代码块标记：
{{
  "questions": [
{example}
  ]
}}"""


def _get_example(type_key: str, score: float) -> str:
    """返回对应题型的JSON示例"""
    s = score
    if type_key in ("single_choice", "multi_choice"):
        ans = "A" if type_key == "single_choice" else "ABD"
        return f'''    {{
      "type": "{type_key}",
      "content": "题干内容（此处填写题目）",
      "options": ["A. 选项一", "B. 选项二", "C. 选项三", "D. 选项四"],
      "answer": "{ans}",
      "analysis": "解析说明",
      "score": {s}
    }}'''
    elif type_key == "true_false":
        return f'''    {{
      "type": "true_false",
      "content": "判断题内容（此处填写题目）",
      "options": [],
      "answer": "×",
      "analysis": "解析说明",
      "score": {s}
    }}'''
    elif type_key == "fill_blank":
        return f'''    {{
      "type": "fill_blank",
      "content": "填空题内容，空格用___表示",
      "options": [],
      "answer": "参考答案",
      "analysis": "解析说明",
      "score": {s}
    }}'''
    elif type_key == "short_answer":
        return f'''    {{
      "type": "short_answer",
      "content": "简答题题目",
      "options": [],
      "answer": "参考答案（详细）",
      "analysis": "评分要点",
      "score": {s}
    }}'''
    elif type_key == "essay":
        return f'''    {{
      "type": "essay",
      "content": "论述题题目",
      "options": [],
      "answer": "参考答案（详细论述）",
      "analysis": "评分标准",
      "score": {s}
    }}'''
    elif type_key == "case_analysis":
        return f'''    {{
      "type": "case_analysis",
      "content": "【案例背景】\\n具体案例描述...\\n\\n【问题】\\n1. 问题一\\n2. 问题二",
      "options": [],
      "answer": "1. 问题一答案\\n2. 问题二答案",
      "analysis": "评分要点",
      "score": {s}
    }}'''
    return ""


def _parse_questions(response: str, type_key: str,
                     score_per: float) -> list:
    """解析AI返回的JSON，过滤只保留指定题型"""
    # 清理markdown代码块
    text = re.sub(r'```(?:json)?', '', response).strip()
    text = text.replace('```', '').strip()

    # 尝试提取JSON
    # 先找最外层花括号
    m = re.search(r'\{.*\}', text, re.DOTALL)
    if not m:
        logger.warning(f"未找到JSON结构，原始返回前200字: {text[:200]}")
        return []

    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        # 尝试修复常见JSON错误（末尾多余逗号）
        fixed = re.sub(r',\s*([}\]])', r'\1', m.group(0))
        try:
            data = json.loads(fixed)
        except Exception:
            logger.warning(f"JSON解析失败: {e}，原始: {text[:300]}")
            return []

    raw = data.get("questions", [])
    questions = []
    for q in raw:
        qt = q.get("type", type_key)
        # 兼容：如果AI返回了不同题型，强制修正为目标题型
        if qt != type_key:
            qt = type_key
        score = float(q.get("score", score_per) or score_per)
        questions.append({
            "q_type":   qt,
            "content":  q.get("content", "").strip(),
            "options":  q.get("options", []),
            "answer":   str(q.get("answer", "")),
            "analysis": q.get("analysis", ""),
            "score":    score,
        })
    return questions


class ExamEngine:
    def __init__(self, ai_provider):
        self.ai = ai_provider
        # 已出题记录，用于跨套去重
        # key: type_key -> list of content前60字
        self._used: dict = {}

    def reset_used(self):
        """重置已出题记录，后续出题不再避免与之前相同"""
        self._used.clear()
        logger.info("已重置出题记录")

    def generate_papers(self, knowledge_texts: dict,
                        config: FullExamConfig,
                        progress_callback=None) -> list:
        combined = self._merge(knowledge_texts)
        papers = []

        for idx in range(1, config.paper_count + 1):
            if progress_callback:
                progress_callback(idx, config.paper_count, f"正在生成第{idx}套试卷...")
            logger.info(f"开始生成第{idx}套试卷")
            paper = self._generate_one(combined, config, idx)
            papers.append(paper)

        return papers

    def _generate_one(self, knowledge: str, config: FullExamConfig,
                      paper_idx: int) -> ExamPaper:
        all_questions = []

        for qt_cfg in config.question_types:
            if not qt_cfg.enabled or qt_cfg.count == 0:
                continue

            type_key   = qt_cfg.type_key
            need_count = qt_cfg.count
            logger.info(f"  [{type_key}] 需要{need_count}题")

            # 分批出题（每批最多 MAX_PER_BATCH 道）
            collected = []
            remaining = need_count

            while remaining > 0:
                batch_size = min(remaining, MAX_PER_BATCH)
                used_for_type = self._used.get(type_key, [])

                prompt = _build_batch_prompt(
                    knowledge, qt_cfg, batch_size,
                    paper_idx, used_for_type, config
                )

                try:
                    response = self.ai.chat(SYSTEM_PROMPT, prompt)
                    batch = _parse_questions(response, type_key, qt_cfg.score_per)
                    logger.info(f"    批次返回{len(batch)}题（需要{batch_size}题）")

                    if not batch:
                        logger.warning(f"    AI返回空结果，跳过此批次")
                        break

                    # 去重过滤（基于内容前50字）
                    used_set = set(self._used.get(type_key, []))
                    new_batch = []
                    for q in batch:
                        key60 = q["content"][:60]
                        if key60 not in used_set:
                            new_batch.append(q)
                            used_set.add(key60)
                    batch = new_batch

                    collected.extend(batch)
                    remaining -= len(batch)

                    # 数量不足时补出（再请求一次）
                    if len(batch) < batch_size and remaining > 0:
                        short = batch_size - len(batch)
                        logger.warning(f"    本批次少{short}题，将在下一批补全")
                        # remaining 已经减去了实际得到的数量，继续循环即可

                except Exception as e:
                    logger.error(f"    [{type_key}] 出题失败: {e}")
                    # 出题失败则用占位题填充，确保总数不受影响
                    if not collected:
                        break
                    # 不够的用已有题目补充（复制最后一题并标注）
                    while len(collected) < need_count:
                        placeholder = dict(collected[-1])
                        placeholder["content"] = f"[备用题{len(collected)+1}] {placeholder['content']}"
                        collected.append(placeholder)
                    remaining = 0
                    break

            # 截断到精确数量
            collected = collected[:need_count]

            # 若仍不足，用第一题补充（极端情况兜底）
            if collected and len(collected) < need_count:
                logger.warning(f"  [{type_key}] 最终只有{len(collected)}题，补全到{need_count}题")
                while len(collected) < need_count:
                    dup = dict(collected[len(collected) % len(collected) if collected else 0])
                    dup["content"] = f"[补全题] " + dup["content"]
                    collected.append(dup)

            # 记录已出题内容
            if type_key not in self._used:
                self._used[type_key] = []
            self._used[type_key].extend(q["content"][:60] for q in collected)

            # 转为 Question 对象
            for q_dict in collected:
                all_questions.append(Question(
                    q_type   = q_dict["q_type"],
                    number   = len(all_questions) + 1,
                    content  = q_dict["content"],
                    options  = q_dict["options"],
                    answer   = q_dict["answer"],
                    analysis = q_dict["analysis"],
                    score    = q_dict["score"],
                ))

            logger.info(f"  [{type_key}] 完成，共{len(collected)}题")

        # 构建试卷标题
        title = config.exam_title
        if config.exam_subtitle:
            title = f"{title}{config.exam_subtitle}"

        return ExamPaper(
            paper_index=paper_idx,
            title=title,
            config=config,
            questions=all_questions,
        )

    def _merge(self, texts: dict, max_chars: int = 12000) -> str:
        parts, total = [], 0
        for fname, content in texts.items():
            part = f"【来源：{fname}】\n{content}"
            if total + len(part) > max_chars:
                rem = max_chars - total
                if rem > 300:
                    parts.append(part[:rem] + "\n...(内容截断)")
                break
            parts.append(part)
            total += len(part)
        return "\n\n".join(parts)
