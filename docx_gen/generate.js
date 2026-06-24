/**
 * 智能出卷系统 - A3横向双栏 Word 生成器
 * 用法: node generate.js <input.json> <output_dir>
 *
 * A3横向: w=23811 DXA, h=16838 DXA  (1mm≈56.69DXA)
 * 页边距: 上下20mm=1134, 左右15mm=851
 * 双栏间距: 10mm=567
 * 可用宽: 23811-851*2=22109, 每栏: (22109-567)/2=10771
 */
'use strict';
const fs   = require('fs');
const path = require('path');
const {
  Document, Packer,
  Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer,
  AlignmentType, PageOrientation, BorderStyle, WidthType,
  TabStopType, PageNumberElement, UnderlineType,
} = require('docx');

// ── 尺寸常量 ─────────────────────────────────────────────────────────────────
const A3_W      = 23811;
const A3_H      = 16838;
const M_TB      = 1134;
const M_LR      = 851;
const COL_GAP   = 567;
const TOTAL_W   = A3_W - M_LR * 2;                    // 22109
const COL_W     = Math.floor((TOTAL_W - COL_GAP) / 2); // 10771

// ── 颜色 ─────────────────────────────────────────────────────────────────────
const C = {
  primary : '1F4E79',
  second  : '2E75B6',
  accent  : '0070C0',
  gray    : '595959',
  lgray   : 'AAAAAA',
  border  : '9DC3E6',
  black   : '000000',
  white   : 'FFFFFF',
};

// ── 边框 ─────────────────────────────────────────────────────────────────────
const bdr  = (color = C.border, sz = 6) => ({ style: BorderStyle.SINGLE, size: sz, color });
const noBdr = () => ({ style: BorderStyle.NONE, size: 0, color: C.white });
const NO_B  = { top: noBdr(), bottom: noBdr(), left: noBdr(), right: noBdr(),
                insideH: noBdr(), insideV: noBdr() };

// ── TextRun 工厂 ─────────────────────────────────────────────────────────────
function tr(text, o = {}) {
  return new TextRun({
    text,
    font : o.bold ? '黑体' : (o.font || '仿宋'),
    size : o.size || 22,
    bold : !!o.bold,
    color: o.color || C.black,
    underline: o.ul ? { type: UnderlineType.SINGLE } : undefined,
  });
}

// ── Paragraph 工厂 ───────────────────────────────────────────────────────────
function para(runs, o = {}) {
  return new Paragraph({
    alignment: o.align || AlignmentType.JUSTIFIED,
    spacing : { before: o.before ?? 40, after: o.after ?? 40, line: o.line ?? 360 },
    indent  : o.indent ? { left: o.indent } : undefined,
    border  : o.border || undefined,
    tabStops: o.tabs   || undefined,
    children: Array.isArray(runs) ? runs : [runs],
  });
}
const emptyP = (before = 60) =>
  new Paragraph({ spacing: { before, after: 0 }, children: [new TextRun('')] });

// ── 罗马数字 ─────────────────────────────────────────────────────────────────
const ROMAN = ['一','二','三','四','五','六','七','八','九','十'];

// ── 题型元数据 ───────────────────────────────────────────────────────────────
const TYPE_NAME = {
  single_choice: '单项选择题',
  multi_choice : '多项选择题',
  true_false   : '判断题',
  fill_blank   : '填空题',
  short_answer : '简答题',
  essay        : '论述题',
  case_analysis: '案例分析题',
};
const TYPE_INST = {
  single_choice: '（每题只有一个正确答案，请将正确选项字母填入括号内）',
  multi_choice : '（每题有两个或两个以上正确答案，全对得满分，漏选得一半分，错选不得分）',
  true_false   : '（请判断下列说法正误，正确填"√"，错误填"×"）',
  fill_blank   : '（请在横线上填写正确答案）',
  short_answer : '（请简明扼要地回答下列问题）',
  essay        : '（请结合所学知识进行系统阐述）',
  case_analysis: '（请认真阅读案例，分析并回答问题）',
};
const TYPE_ORDER = ['single_choice','multi_choice','true_false',
                    'fill_blank','short_answer','essay','case_analysis'];

// ── 页眉 ─────────────────────────────────────────────────────────────────────
function makeHeader(paper, totalScore, isAns) {
  const suffix = isAns ? '【参考答案与解析】' : '';
  return new Header({ children: [
    new Paragraph({
      border  : { bottom: bdr(C.second, 12) },
      spacing : { before: 0, after: 100 },
      tabStops: [{ type: TabStopType.RIGHT, position: TOTAL_W }],
      children: [
        tr(`${paper.title}${suffix}`, { bold:true, size:28, color:C.primary }),
        new TextRun({ text:'\t', font:'仿宋' }),
        tr(`科目：${paper.subject||'综合'}    考试时间：${paper.exam_time||120}分钟    总分：${totalScore}分`,
           { size:20, color:C.gray }),
      ],
    }),
  ]});
}

// ── 页脚 ─────────────────────────────────────────────────────────────────────
function makeFooter(isAns) {
  const CENTER = Math.floor(TOTAL_W / 2);
  return new Footer({ children: [
    new Paragraph({
      border  : { top: bdr(C.border, 6) },
      spacing : { before: 60, after: 0 },
      tabStops: [
        { type: TabStopType.CENTER, position: CENTER },
        { type: TabStopType.RIGHT,  position: TOTAL_W },
      ],
      children: [
        tr(isAns ? '答案仅供参考，请以实际评分标准为准' : '请在规定时间内完成，不得使用任何辅助工具',
           { size:18, color:C.gray }),
        new TextRun({ text:'\t', font:'仿宋' }),
        tr('第 ', { size:20 }),
        new PageNumberElement(),
        tr(' 页', { size:20 }),
        new TextRun({ text:'\t', font:'仿宋' }),
        tr(isAns ? '答案卷' : '试题卷', { size:18, color:C.gray }),
      ],
    }),
  ]});
}

// ── 考生信息栏 ───────────────────────────────────────────────────────────────
function makeInfoBar(title, isAns) {
  const rows = [
    para([tr(title, { bold:true, size:34, color:C.primary })],
         { align: AlignmentType.CENTER, before:0, after:60 }),
  ];
  if (isAns) {
    rows.push(para([tr('参考答案与解析', { bold:true, size:26, color:C.accent })],
                   { align: AlignmentType.CENTER, before:0, after:120 }));
  } else {
    const fields = ['姓　　名：___________','准考证号：___________',
                    '班　　级：___________','考试成绩：___________'];
    const cw = Math.floor(TOTAL_W / fields.length);
    rows.push(new Table({
      width: { size: TOTAL_W, type: WidthType.DXA },
      columnWidths: fields.map(() => cw),
      borders: NO_B,
      rows: [new TableRow({ children: fields.map(f => new TableCell({
        borders: { ...NO_B, bottom: bdr(C.border, 6) },
        width  : { size: cw, type: WidthType.DXA },
        margins: { top:40, bottom:40, left:60, right:60 },
        children: [para([tr(f, { size:20 })], { before:0, after:0 })],
      }))})],
    }));
    rows.push(emptyP(80));
  }
  return rows;
}

// ── 题型大标题 ───────────────────────────────────────────────────────────────
function sectionHeader(idx, typeKey, totalScore) {
  const label = `${ROMAN[idx]||idx+1}、${TYPE_NAME[typeKey]||typeKey}`;
  return [
    new Paragraph({
      spacing: { before:180, after:60 },
      border : { bottom: bdr(C.second, 10) },
      children: [
        tr(label, { bold:true, size:26, color:C.primary }),
        tr(`  （共${totalScore}分）`, { size:20, color:C.gray }),
      ],
    }),
    para([tr(TYPE_INST[typeKey]||'', { size:20, color:C.gray })], { before:20, after:60 }),
  ];
}

// ── 选择题 ───────────────────────────────────────────────────────────────────
function renderChoice(q, num, showAns) {
  const items = [];
  items.push(para([
    tr(`${num}. `, { bold:true }),
    tr(q.content),
    tr(`（${q.score}分）`, { size:20, color:C.gray }),
  ], { before:60, line:380 }));

  if (q.options && q.options.length) {
    if (q.options.length <= 2) {
      q.options.forEach(opt =>
        items.push(para([tr(opt,{size:21})], { indent:420, before:20, after:20 }))
      );
    } else {
      const hw = Math.floor((COL_W - 500) / 2);
      for (let i = 0; i < q.options.length; i += 2) {
        const L = q.options[i]   || '';
        const R = q.options[i+1] || '';
        items.push(new Table({
          width: { size: COL_W - 400, type: WidthType.DXA },
          columnWidths: [hw, hw],
          borders: NO_B,
          rows: [new TableRow({ children: [L, R].map(txt => new TableCell({
            borders: NO_B,
            width  : { size: hw, type: WidthType.DXA },
            margins: { top:20, bottom:20, left:420, right:80 },
            children: [para([tr(txt,{size:21})], { before:0, after:0 })],
          }))})],
        }));
      }
    }
  }

  if (showAns) {
    items.push(para([tr('【答案】',{bold:true,color:C.accent}), tr(q.answer,{color:C.accent})],
                    { indent:420, before:20 }));
    if (q.analysis)
      items.push(para([tr('【解析】',{bold:true,color:C.gray}), tr(q.analysis,{size:20,color:C.gray})],
                      { indent:420, before:0, after:80 }));
  }
  return items;
}

// ── 判断题 ───────────────────────────────────────────────────────────────────
function renderTF(q, num, showAns) {
  const items = [];
  items.push(para([
    tr(`${num}. `,{bold:true}), tr(q.content),
    tr('  （    ）',{size:21}),
    tr(`（${q.score}分）`,{size:20,color:C.gray}),
  ], { before:60, line:380 }));
  if (showAns) {
    items.push(para([tr('【答案】',{bold:true,color:C.accent}), tr(q.answer,{color:C.accent})],
                    { indent:420, before:20, after:80 }));
    if (q.analysis)
      items.push(para([tr('【解析】',{bold:true,color:C.gray}), tr(q.analysis,{size:20,color:C.gray})],
                      { indent:420, before:0, after:80 }));
  }
  return items;
}

// ── 填空题 ───────────────────────────────────────────────────────────────────
function renderFill(q, num, showAns) {
  const items = [];
  items.push(para([
    tr(`${num}. `,{bold:true}), tr(q.content),
    tr(`（${q.score}分）`,{size:20,color:C.gray}),
  ], { before:60, line:400 }));
  if (showAns)
    items.push(para([tr('【答案】',{bold:true,color:C.accent}), tr(q.answer,{color:C.accent})],
                    { indent:420, before:20, after:80 }));
  return items;
}

// ── 主观题（简答/论述/案例）──────────────────────────────────────────────────
function renderOpen(q, num, showAns) {
  const items = [];
  const lines = (q.content || '').split('\n');
  items.push(para([
    tr(`${num}. `,{bold:true}), tr(lines[0]||''),
    tr(`（${q.score}分）`,{size:20,color:C.gray}),
  ], { before:80, line:380 }));
  for (let i = 1; i < lines.length; i++)
    if (lines[i].trim())
      items.push(para([tr(lines[i])], { indent:420, before:20 }));

  if (!showAns) {
    const n = q.q_type==='case_analysis' ? 14 : q.q_type==='essay' ? 12 : 7;
    for (let i = 0; i < n; i++)
      items.push(new Paragraph({
        spacing: { before:20, after:20, line:520 },
        border : { bottom: { style:BorderStyle.SINGLE, size:4, color:'CCCCCC' } },
        children: [new TextRun('')],
      }));
    items.push(emptyP(60));
  } else {
    items.push(para([tr('【参考答案】',{bold:true,color:C.accent})], { before:60 }));
    (q.answer||'').split('\n').forEach(l => {
      if (l.trim()) items.push(para([tr(l,{color:C.accent})], { indent:420, before:20 }));
    });
    if (q.analysis) {
      items.push(para([tr('【评分要点】',{bold:true,color:C.gray})], { before:40 }));
      items.push(para([tr(q.analysis,{size:20,color:C.gray})], { indent:420, before:10 }));
    }
    items.push(emptyP(80));
  }
  return items;
}

function renderQ(q, num, showAns) {
  switch (q.q_type) {
    case 'single_choice':
    case 'multi_choice' : return renderChoice(q, num, showAns);
    case 'true_false'   : return renderTF(q, num, showAns);
    case 'fill_blank'   : return renderFill(q, num, showAns);
    default             : return renderOpen(q, num, showAns);
  }
}

// ── 构建正文内容 ─────────────────────────────────────────────────────────────
function buildChildren(paper, showAns) {
  const children = [];
  makeInfoBar(paper.title, showAns).forEach(p => children.push(p));

  // 分组
  const groups = {};
  (paper.questions || []).forEach(q => {
    (groups[q.q_type] = groups[q.q_type] || []).push(q);
  });

  const present = TYPE_ORDER.filter(k => groups[k] && groups[k].length);
  let globalNum = 1;

  present.forEach((typeKey, idx) => {
    const qs    = groups[typeKey];
    const total = qs.reduce((s, q) => s + (q.score || 0), 0);
    sectionHeader(idx, typeKey, total).forEach(p => children.push(p));
    qs.forEach(q => renderQ(q, globalNum++, showAns).forEach(p => children.push(p)));
  });

  return children;
}

// ── 构建 Document ────────────────────────────────────────────────────────────
function buildDoc(paper, showAns) {
  const total = (paper.questions || []).reduce((s, q) => s + (q.score || 0), 0);
  return new Document({
    sections: [{
      properties: {
        page: {
          size  : { width: A3_H, height: A3_W, orientation: PageOrientation.LANDSCAPE },
          margin: { top: M_TB, right: M_LR, bottom: M_TB, left: M_LR },
        },
        // ★ 关键：column 必须在 properties 顶层，不能放在 page 内
        column: { space: COL_GAP, count: 2, equalWidth: true },
      },
      headers: { default: makeHeader(paper, total, showAns) },
      footers: { default: makeFooter(showAns) },
      children: buildChildren(paper, showAns),
    }],
  });
}

// ── 主入口 ───────────────────────────────────────────────────────────────────
async function main() {
  const [,, inputPath, outputDir] = process.argv;
  if (!inputPath || !outputDir) {
    console.error('用法: node generate.js <input.json> <output_dir>');
    process.exit(1);
  }

  const data   = JSON.parse(fs.readFileSync(inputPath, 'utf-8'));
  const papers = data.papers || [];

  fs.mkdirSync(outputDir, { recursive: true });
  const results = [];

  for (const paper of papers) {
    const safe = paper.title.replace(/[\\/:*?"<>|]/g, '_');

    const examBuf = await Packer.toBuffer(buildDoc(paper, false));
    const examPath = path.join(outputDir, `${safe}_试题.docx`);
    fs.writeFileSync(examPath, examBuf);

    const ansBuf  = await Packer.toBuffer(buildDoc(paper, true));
    const ansPath  = path.join(outputDir, `${safe}_答案.docx`);
    fs.writeFileSync(ansPath, ansBuf);

    results.push({ paper: examPath, answer: ansPath });
    console.log(`✓ ${safe}`);
  }

  fs.writeFileSync(path.join(outputDir, '_results.json'), JSON.stringify(results, null, 2));
  console.log('ALL_DONE');
}

main().catch(err => {
  console.error('生成失败:', err.message);
  process.exit(1);
});
