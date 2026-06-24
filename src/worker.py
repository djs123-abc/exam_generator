"""后台工作线程"""
import os, logging
from PyQt6.QtCore import QThread, pyqtSignal
from ai_providers import AIConfig, AIProvider
from doc_reader import read_file, read_url, read_directory
from exam_engine import ExamEngine
from exam_config_schema import FullExamConfig
from docx_writer import generate_docx

logger = logging.getLogger(__name__)


class GenerationWorker(QThread):
    progress       = pyqtSignal(int, str)
    log_line       = pyqtSignal(str)
    finished_ok    = pyqtSignal(list)
    finished_error = pyqtSignal(str)

    def __init__(self, ai_config: AIConfig, exam_config: FullExamConfig,
                 file_paths: list, urls: list, dir_path: str,
                 output_dir: str, engine: ExamEngine = None):
        super().__init__()
        self.ai_config   = ai_config
        self.exam_config = exam_config
        self.file_paths  = file_paths
        self.urls        = urls
        self.dir_path    = dir_path
        self.output_dir  = output_dir
        # 共享 engine 实例（保持已出题记录，用于去重）
        self._engine     = engine
        self._cancelled  = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            self._run()
        except Exception as e:
            logger.exception('生成流程异常')
            self.finished_error.emit(str(e))

    def _run(self):
        # ── Step1: 读取素材 ──────────────────────────────────────────────────
        texts: dict = {}
        total_src = len(self.file_paths) + len(self.urls) + (1 if self.dir_path else 0)
        if total_src == 0:
            self.finished_error.emit('未提供任何素材，请添加文件、URL 或目录')
            return

        self.progress.emit(2, '开始读取素材...')
        done = 0

        for fp in self.file_paths:
            if self._cancelled: return
            name = os.path.basename(fp)
            self.log_line.emit(f'📄 读取文件: {name}')
            try:
                content = read_file(fp)
                texts[name] = content
                self.log_line.emit(f'   ✅ {len(content):,} 字符')
            except Exception as e:
                self.log_line.emit(f'   ⚠️ 读取失败: {e}')
            done += 1
            self.progress.emit(int(done / total_src * 18), f'素材读取 {done}/{total_src}')

        for url in self.urls:
            if self._cancelled: return
            self.log_line.emit(f'🌐 抓取URL: {url[:60]}...')
            try:
                content = read_url(url)
                texts[url] = content
                self.log_line.emit(f'   ✅ {len(content):,} 字符')
            except Exception as e:
                self.log_line.emit(f'   ⚠️ 抓取失败: {e}')
            done += 1
            self.progress.emit(int(done / total_src * 18), f'素材读取 {done}/{total_src}')

        if self.dir_path:
            if self._cancelled: return
            self.log_line.emit(f'📁 扫描目录: {self.dir_path}')
            try:
                def _dir_cb(cur, total, fp):
                    self.log_line.emit(f'   📄 {os.path.basename(fp)}')
                dir_texts = read_directory(self.dir_path, _dir_cb)
                texts.update(dir_texts)
                self.log_line.emit(f'   ✅ 共 {len(dir_texts)} 个文件')
            except Exception as e:
                self.log_line.emit(f'   ⚠️ 目录读取失败: {e}')

        if not texts:
            self.finished_error.emit('所有素材读取失败，无法出题')
            return

        total_chars = sum(len(v) for v in texts.values())
        self.log_line.emit(f'\n📊 素材汇总: {len(texts)} 个来源，共 {total_chars:,} 字符')

        # ── Step2: 生成试卷 ──────────────────────────────────────────────────
        if self._cancelled: return
        self.progress.emit(20, '初始化AI...')
        n_keys = len(self.ai_config.api_keys)
        self.log_line.emit(
            f'\n🤖 {self.ai_config.provider} / {self.ai_config.model}'
            f'  ({n_keys}个Key，{self.ai_config.poll_strategy}轮询)'
            f'  超时:{self.ai_config.timeout_read:.0f}s，重试:{self.ai_config.max_retries}次'
        )

        # 使用传入的共享 engine（保持题目记录）或新建
        if self._engine is None:
            self._engine = ExamEngine(AIProvider(self.ai_config))
        else:
            # 更新 AI provider（Key 可能已更新）
            self._engine.ai = AIProvider(self.ai_config)

        total_papers = self.exam_config.paper_count
        # 统计需要出的总题数
        total_q = sum(qt.count for qt in self.exam_config.question_types if qt.enabled)
        self.log_line.emit(f'📋 计划出 {total_papers} 套试卷，每套 {total_q} 道题\n')

        papers = []
        for idx in range(1, total_papers + 1):
            if self._cancelled: return
            pct = 20 + int((idx - 1) / total_papers * 65)
            self.progress.emit(pct, f'正在生成第 {idx}/{total_papers} 套试卷...')
            self.log_line.emit(f'─── 第 {idx} 套 ───')
            try:
                paper = self._engine._generate_one(
                    self._engine._merge(texts),
                    self.exam_config,
                    idx,
                )
                papers.append(paper)
                actual = len(paper.questions)
                self.log_line.emit(f'✅ 第{idx}套完成，共 {actual} 道题')
            except Exception as e:
                self.log_line.emit(f'❌ 第{idx}套失败: {e}')
                self.finished_error.emit(f'第{idx}套试卷生成失败:\n{e}')
                return

        # ── Step3: 生成Word ──────────────────────────────────────────────────
        if self._cancelled: return
        self.progress.emit(87, '正在生成 Word 文档...')
        self.log_line.emit('\n📝 生成 Word 文档...')

        def _docx_cb(cur, total, msg):
            pct = 87 + int(cur / max(total, 1) * 11)
            self.progress.emit(pct, msg)

        results = generate_docx(papers, self.output_dir, _docx_cb)

        self.progress.emit(100, '全部完成！')
        self.log_line.emit(f'\n🎉 完成！输出目录: {self.output_dir}')
        for r in results:
            self.log_line.emit(f'   📄 {os.path.basename(r["paper"])}')
            self.log_line.emit(f'   📋 {os.path.basename(r["answer"])}')

        self.finished_ok.emit(results)
