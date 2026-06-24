# 智能出卷系统

基于 AI 大模型的全自动出卷工具，支持从 PDF/Word/图片/URL/目录等多种来源读取知识材料，自动生成多套规范试卷（A3横向双栏，可直接打印），答案独立存放。

---

## 功能特性

| 功能           | 说明 |
|----------------|------|
| **多来源素材** | PDF、Word、Excel、PPT、图片(OCR)、TXT、URL网页、指定目录 |
| **OCR 识别**   | 集成 PaddleOCR，支持中文图片/扫描件识别 |
| **多AI支持**   | Anthropic、OpenAI、DeepSeek、通义千问、文心一言、豆包、Kimi、GLM、星火、Gemini、Groq 及自定义端点 |
| **7种题型**    | 单选、多选、判断、填空、简答、论述、案例分析 |
| **不限套数**   | 支持同一知识库生成多套不重复试卷 |
| **专业排版**   | A3横向双栏，页眉页脚页码，考生信息栏，直接打印 |
| **答案独立**   | 试题卷和答案卷分开，每题含解析 |

---

## 环境要求

- Python 3.10+
- Node.js 18+（用于生成 Word 文档）
- Windows 10/11（建议，macOS/Linux 也可运行但未完整测试）

---

## 快速开始

### 方式一：直接运行（开发模式）

```bash
# 1. 克隆/解压项目目录
cd exam_generator

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 安装 Node.js 依赖
cd docx_gen
npm install
cd ..

# 4. 启动程序
python src/app.py
```

### 方式二：打包为 exe（Windows）

```batch
:: 双击运行
build.bat
```

打包完成后，`dist\智能出卷系统\智能出卷系统.exe` 即为可分发程序。

---

## 使用说明

### 1. AI配置
- 打开程序，点击「AI配置」标签
- 选择 AI 提供商，填入对应的 API Key
- 点击「测试连接」验证配置

### 2. 添加素材
支持三种方式（可混合使用）：
- **上传文件**：点击「添加文件」或拖拽文件到列表
- **URL链接**：每行填一个网页地址
- **指定目录**：选择存放知识材料的文件夹，自动扫描所有支持文件

### 3. 配置题型
在「题型配置」标签设置各题型的**题数**和**每题分值**，右侧实时显示总分。

### 4. 试卷设置
- 填写试卷名称、科目、考试时间
- 设置**出卷套数**（不限，每套题目不重复）
- 选择难度等级
- 选择输出目录

### 5. 开始出卷
点击「🚀 开始出卷」，右侧日志面板实时显示进度。

---

## 支持的AI提供商

| 提供商 | API Key 获取 |
|--------|-------------|
| Anthropic Claude | https://console.anthropic.com |
| OpenAI GPT | https://platform.openai.com |
| DeepSeek | https://platform.deepseek.com |
| 通义千问 | https://dashscope.aliyuncs.com |
| 文心一言 | https://cloud.baidu.com/product/wenxinworkshop |
| 豆包 | https://www.volcengine.com/product/doubao |
| Kimi | https://platform.moonshot.cn |
| 智谱 GLM | https://open.bigmodel.cn |
| 讯飞星火 | https://xinghuo.xfyun.cn |
| Google Gemini | https://aistudio.google.com |
| Groq | https://console.groq.com |
| 自定义端点 | 任何兼容 OpenAI API 格式的服务 |

---

## 输出文件说明

每套试卷输出两个 Word 文件：

```
试卷输出/
├── 综合测试卷（第1套）_试题.docx   ← A3横向双栏，考生答题卷
├── 综合测试卷（第1套）_答案.docx   ← 参考答案与解析
├── 综合测试卷（第2套）_试题.docx
└── 综合测试卷（第2套）_答案.docx
```

**打印建议**：打印时选择 A3 纸，横向，不缩放，直接打印即可。

---

## 关于 PaddleOCR

PaddleOCR 体积较大（约 1GB），默认不强制安装。
如需识别图片或扫描版 PDF，请手动安装：

```bash
pip install paddlepaddle paddleocr
```

安装后重启程序即自动启用。

---

## 目录结构

```
exam_generator/
├── src/
│   ├── app.py              # 程序入口
│   ├── main_window.py      # 主窗口
│   ├── ui_settings.py      # AI配置面板
│   ├── ui_question_types.py# 题型配置面板
│   ├── ui_source.py        # 素材来源面板
│   ├── worker.py           # 后台工作线程
│   ├── ai_providers.py     # AI提供商抽象层
│   ├── doc_reader.py       # 文档读取模块
│   ├── exam_engine.py      # 出卷引擎
│   ├── docx_writer.py      # Word生成封装
│   └── settings.py         # 设置持久化
├── docx_gen/
│   ├── generate.js         # Node.js Word生成脚本
│   └── package.json
├── requirements.txt
├── exam_generator.spec     # PyInstaller配置
├── build.bat               # Windows一键打包
└── README.md
```

---

## 常见问题

**Q: 出题内容与素材不相关？**
A: 检查素材是否成功读取（查看日志），适当增加素材量，或在「特殊要求」中补充说明。

**Q: 生成速度很慢？**
A: 受AI接口响应速度影响。多套试卷会依次调用AI，建议使用 DeepSeek / Groq 等响应较快的服务。

**Q: 图片识别效果差？**
A: 确保安装了 PaddleOCR；图片分辨率建议 300dpi 以上，中文识别效果最佳。

**Q: 自定义端点如何填写？**
A: 选择「自定义端点」，在「API端点」处填写完整 URL（如 `http://localhost:11434/v1`），模型名手动输入。

**Q: exe 运行需要安装 Node.js 吗？**
A: exe 打包已将 docx_gen 目录打包进去，但仍需要目标机器安装 Node.js。可考虑将 Node.js 便携版一起分发。
