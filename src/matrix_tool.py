"""科研矩阵表生长工具（matrix_tool.py）

把"种子论文 → GROBID 解析 → 引用上下文抽取 → 矩阵表"的流水线做成可持续生长的工具：
每加一篇种子论文，自动解析、抽取、跨论文去重合并、按"总内部引用次数"降序重建整张表。

用法（用 miniconda 的 python，不要用裸 python）:
  python matrix_tool.py init                                                 # 首次：迁移现有种子论文并自检对账
  ... matrix_tool.py add data/seed_papers/新论文.pdf [--key KEY] [--force]    # 加新种子（需校园 VPN 连 GROBID）
  ... matrix_tool.py add X.pdf --from-tei 现成.tei.xml                        # 离线入口：直接用现成 TEI，无需 VPN
  ... matrix_tool.py rebuild                                                 # 改过 data/config 或译文后全量重建
  ... matrix_tool.py export-untranslated                                     # 导出缺译句子清单
  ... matrix_tool.py import-translations 译文.json                           # 回填译文（{hash:中文} 或 {英文句:中文}）
  ... matrix_tool.py remove KEY                                              # 注销某篇种子并重建
  ... matrix_tool.py status                                                  # 查看现状

架构约定（为将来云协作预留，见 README）:
  - data/state/papers/<KEY>.json 是唯一事实源；xlsx 只是导出物，永远不要手改
  - data/config 与 data/state 下均为 git 友好格式（UTF-8、相对路径、无易变时间戳、原子写入）
  - 核心逻辑（抽取/并集/排序/渲染）为纯函数，CLI 只是薄壳，可整体被 API/Web 替代
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import sys
import time
import traceback
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag  # bs4 顶层转引出未声明 __all__，从定义模块导入以免 Pylance 报未导出
try:
    from .util_get_current_time import now_beijing_iso_no_tz
except ImportError:  # 支持 python src/matrix_tool.py 直接运行
    from util_get_current_time import now_beijing_iso_no_tz

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROOT = PROJECT_ROOT
DATA_DIR = ROOT / "data"
CONFIG_DIR = DATA_DIR / "config"
STATE_DIR = DATA_DIR / "state"
PAPERS_STATE_DIR = STATE_DIR / "papers"
INPUT_SEED_DIR = DATA_DIR / "seed_papers"
OUTPUT_DIR = DATA_DIR / "exports"
LOG_DIR = ROOT / "log"

SCHEMA_VERSION = 1
PAPERS_SCHEMA_VERSION = 2   # data/state/papers/<KEY>.json 结构升级（上下文窗口 + 引用标记）
TRANS_POOL = STATE_DIR / "translations_by_hash.json"

COL_HEADER_COUNT = "内部提及次数"
COL_HEADER_TOTAL = "总内部引用次数"
COL_HEADER_ABBREV = "方法简写"
SENT_SEP = "\n———————————\n"

# 上下文窗口默认值（前后各几句）；0 = 只显示引用句本身。
# 可在 data/config/project.json 的 context_window 段覆盖，或用 rebuild --window 临时覆盖。
DEFAULT_CONTEXT_WINDOW = {"before": 2, "after": 2}

# 自动翻译后端（免费、无需 key）：MyMemory 公共接口，改 data/config/project.json 的 translation 段可换。
DEFAULT_TRANSLATION = {
    "engine": "mymemory",
    "endpoint": "https://api.mymemory.translated.net/get",
    "source_lang": "en",
    "target_lang": "zh-CN",
    "enabled": True,
    "timeout": 15,
    "delay": 0.2,        # 串行请求间延迟（秒），避免触发免费限流
    "max_per_run": 500,  # 单次重建最多自动翻译的句数上限
}


# ---------------------------------------------------------------- I/O 工具

def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _atomic_write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)


def write_json(path, obj):
    _atomic_write_text(Path(path), json.dumps(obj, ensure_ascii=False, indent=1) + "\n")


def _hash8(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()[:8]


def _beijing_date() -> str:
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")


def _setup_logging(command: str) -> logging.Logger:
    """配置按日 JSON Lines 日志；日志失败不能阻断主命令。"""
    logger = logging.getLogger("matrix_tool")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        date_key = datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d")
        log_path = LOG_DIR / f"matrix_tool_{date_key}.log"
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    except OSError:
        logger.addHandler(logging.NullHandler())

    return logger


def _log_event(logger: logging.Logger, event: str, **fields) -> None:
    payload = {"schema_version": 1, "event": event, **fields}
    logger.info(json.dumps(payload, ensure_ascii=False, default=str))


# ---------------------------------------------------------- 正文处理核心（纯函数）
# 以下抽取/分句/清洗逻辑与 build_matrix.py 保持一致，保证译文哈希键稳定。

ABBREVIATIONS = [
    "et al.", "e.g.", "i.e.", "vs.", "cf.", "Fig.", "Figs.", "Eq.", "Eqs.",
    "Sec.", "Tab.", "No.", "w.r.t.", "a.k.a.", "resp.", "approx.", "Mr.", "Dr.",
]
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\"'])")

NOISE_PATTERNS = [
    re.compile(r"Proceedings of the \d+(?:st|nd|rd|th)[^.]*?\.?\s*Copyright \d+\s*by the author\(s\)\.?"),
    re.compile(r"Copyright \d+\s*by the author\(s\)\.?"),
    re.compile(r"arXiv:\d{4}\.\d{4,5}(v\d+)?"),
]

# 引用标记可能出现的文本容器（段落/脚注/图表标题）
CONTEXT_CONTAINERS = {"p", "note", "caption", "figDesc", "head"}
MIN_SENT_LEN = 40


def normalize_title(title):
    """标题归一化键：小写、只留字母数字，用作跨论文去重的行 ID。"""
    return re.sub(r"[^a-z0-9]+", "", title.lower())


def is_garbage_title(title):
    """过滤 GROBID 解析出的伪标题（如 "1 others"）。"""
    t = title.strip().lower()
    return (not t) or bool(re.fullmatch(r"\d+(\s+others)?|no title", t))


def clean_context(text):
    """去掉引用标记占位符并清理残留的括号/空格伪影。"""
    text = re.sub(r"\s*⟦\d+⟧", "", text)
    text = re.sub(r"\(\s*;[^)]*\)", "", text)
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"\(\s*[.;]\s*\)", "", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip(" \t,;")


def clean_context_keep_markers(text):
    """同 clean_context，但保留 [[n]] 翻译占位符（用于引用句）。"""
    text = re.sub(r"\s*⟦\d+⟧", "", text)
    text = re.sub(r"\(\s*;[^)]*\)", "", text)
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"\(\s*[.;]\s*\)", "", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip(" \t,;")


def _marker_label(ref_elem) -> str:
    """取引用标记在原文里的可见文本（如 "(Yao et al., 2023)" / "[12]"），供展示。"""
    label = ref_elem.get_text(" ", strip=True) if ref_elem is not None else ""
    label = re.sub(r"\s{2,}", " ", label).strip()
    return label or "[ref]"


def _text_with_markers(full_text: str, spans: list) -> list:
    """把 full_text 里的引用标记替换成 ⟦i⟧ 占位符，返回片段列表（供 join）。"""
    parts, last = [], 0
    for i, span in enumerate(spans):
        s, e = span[0], span[1]
        parts.append(full_text[last:s])
        parts.append(f"⟦{i}⟧")
        last = e
    parts.append(full_text[last:])
    return parts


def _wrap_first_alias(text: str, alias: str) -> str:
    """在句子里首次出现的别名之后插入 [[0]] 占位符（保留别名词本身）。"""
    low = text.lower()
    p = low.find(alias.lower())
    if p < 0:
        return text
    end = p + len(alias)
    return clean_context_keep_markers(text[:end] + "[[0]]" + text[end:])


def build_window_block(sentences, spans, target, before, after):
    """在某个容器内，为 target 构造"上下文窗口"块。

    sentences: [(start, end, text), ...]，text 里含 ⟦i⟧ 占位符（i 为 spans 下标）
    spans: [(start, end, target, ref_elem), ...]
    target: 当前文献 id
    返回 {sentences: [ {text, cite, markers:[{pos,label}]}, ... ]}
    或 None（该容器内没有引用 target 的句子）。
    """
    # 找出引用 target 的句子下标（一个句子可能含多个该 target 的标记）
    cite_sent_idx = []
    span_pos_in_sent = defaultdict(list)   # 句子下标 -> [(span下标, 句内相对位置)]
    for si, (s, e, _) in enumerate(sentences):
        for m in re.finditer(r"⟦(\d+)⟧", sentences[si][2]):
            if spans[int(m.group(1))][2] != target:
                continue
            if si not in cite_sent_idx:
                cite_sent_idx.append(si)
            span_pos_in_sent[si].append(int(m.group(1)))
    if not cite_sent_idx:
        return None

    lo = max(0, min(cite_sent_idx) - before)
    hi = min(len(sentences) - 1, max(cite_sent_idx) + after)
    # 窗口为 0 时只保留引用句本身（不把中间的非引用句一起并入）
    if before == 0 and after == 0:
        xs = sorted(cite_sent_idx)
    else:
        xs = list(range(lo, hi + 1))

    block_sents = []
    for si in xs:
        raw = sentences[si][2]
        is_cite = si in cite_sent_idx
        if is_cite:
            # 本句内 target 的标记换成 [[k]] 占位符（k 从 0 递增），其余标记清掉
            marks = []
            def repl(m, _raw=raw):
                i = int(m.group(1))
                if spans[i][2] == target:
                    k = len(marks)
                    marks.append({"pos": k, "label": _marker_label(spans[i][3])})
                    return f"[[{k}]]"
                return ""
            text = re.sub(r"⟦(\d+)⟧", repl, raw)
            text = clean_context_keep_markers(text)
            block_sents.append({"text": text, "cite": True, "markers": marks})
        else:
            block_sents.append({"text": clean_context(raw), "cite": False, "markers": []})
    block_sents = [x for x in block_sents if x["text"]]
    if not block_sents:
        return None
    return {"sentences": block_sents}


def apply_noise_filters(text):
    for pat in NOISE_PATTERNS:
        text = pat.sub(" ", text)
    return text


def mask_abbreviations(text):
    for abbr in ABBREVIATIONS:
        text = text.replace(abbr, abbr.replace(".", "∮"))
    text = re.sub(r"(\d)\.(\d)", r"\1∮\2", text)
    return text


def unmask(text):
    return text.replace("∮", ".")


def extract_paragraph_with_offsets(p):
    """把容器拼成纯文本，记录每个 bibr 引用标记的字符区间及其元素对象。"""
    parts, spans = [], []
    pos = 0

    def walk(node):
        nonlocal pos
        for child in node.children:
            if isinstance(child, NavigableString):
                s = str(child)
                parts.append(s)
                pos += len(s)
            elif isinstance(child, Tag):
                if child.name == "ref" and child.get("type") == "bibr":
                    start = pos
                    inner = child.get_text()
                    parts.append(inner)
                    pos += len(inner)
                    spans.append((start, pos, child.get("target", "").lstrip("#"), child))
                else:
                    walk(child)

    walk(p)
    return "".join(parts), spans


def split_sentences_with_offsets(text):
    """分句并返回 [(start, end, sentence), ...]，偏移基于传入文本本身。"""
    masked = mask_abbreviations(text)
    out, start = [], 0
    for m in SENT_SPLIT.finditer(masked):
        out.append((start, m.end(), text[start:m.end()]))
        start = m.end()
    out.append((start, len(masked), text[start:]))
    return [(s, e, x) for s, e, x in out if x.strip()]


def _spans_meta(spans):
    return [(s[1], s[2]) for s in spans]


def extract_paper(paper_key: str, tei_text: str, alias_map: dict | None = None,
                  window: tuple[int, int] | None = None):
    """从一篇种子的 GROBID TEI XML 抽出：参考文献元数据 + 每条文献的上下文窗口。

    alias_map: {xml_id: [正文别名, ...]} —— GROBID 漏打引用标记、但正文以方法名
    提及的文献，用别名在正文里搜索补齐（读自 data/config/alias_mentions.json）。
    window: (before, after) —— 每条引用的上下文窗口取同段落内前后各几句。
    产出 contexts[target] = {"count": 提及次数, "blocks": [窗口块, ...]}，
    每个块为 {"sentences": [{"text","cite","markers"}, ...]}。
    """
    before, after = window or (DEFAULT_CONTEXT_WINDOW["before"], DEFAULT_CONTEXT_WINDOW["after"])
    soup = BeautifulSoup(tei_text, "xml")

    # 参考文献列表（listBibl 内的才是文献，header 里的 biblStruct 是论文自身）
    list_bibl = soup.find("listBibl")
    refs_meta = {}
    for bibl in (list_bibl.find_all("biblStruct") if list_bibl else []):
        xml_id = bibl.get("xml:id")
        if not xml_id:
            continue
        t = bibl.find("title", attrs={"level": "a"}) or bibl.find("title")
        year = ""
        date = bibl.find("date")
        if date and date.get("when"):
            year = date.get("when")[:4]
        refs_meta[xml_id] = {"title": t.get_text(" ", strip=True) if t else "",
                             "year": year}

    body = soup.find("body")
    contexts = defaultdict(lambda: {"count": 0, "blocks": []})
    if body is None:
        return {"refs_meta": refs_meta, "contexts": {}}

    # 每个 bibr 标记向上找最近的文本容器，按容器分组；嵌套时只由"最近的容器"
    # 负责，避免重复计数
    groups = defaultdict(list)   # id(container) -> [ref, ...]
    owner = {}                   # id(ref) -> id(container)
    for ref in body.find_all("ref", attrs={"type": "bibr"}):
        anc = ref.find_parent(CONTEXT_CONTAINERS)
        container = anc if anc is not None else ref
        groups[id(container)].append(ref)
        owner[id(ref)] = id(container)

    for cid, refs in groups.items():
        container = refs[0].find_parent(CONTEXT_CONTAINERS) or refs[0]
        full_text, spans = extract_paragraph_with_offsets(container)
        spans = [s for s in spans if owner.get(id(s[3])) == cid]
        if not spans:
            continue
        # 先把标记替换成 ⟦i⟧ 占位符（位置稳定），再做噪声过滤、分句
        ph_text, last = [], 0
        for i, span in enumerate(spans):
            s, e = span[0], span[1]
            ph_text.append(full_text[last:s])
            ph_text.append(f"⟦{i}⟧")
            last = e
        ph_text.append(full_text[last:])
        ph_text = apply_noise_filters("".join(ph_text))

        sentences = split_sentences_with_offsets(ph_text)
        if not sentences:
            continue

        # 该容器内涉及的 target（去重、保序）
        targets = []
        for _, target in _spans_meta(spans):
            if target and target in refs_meta and target not in targets:
                targets.append(target)

        for target in targets:
            # 统计次数：该容器内引用 target 的标记数（与旧口径一致）
            cnt = sum(1 for _, t in _spans_meta(spans) if t == target)
            contexts[target]["count"] += cnt
            blk = build_window_block(sentences, spans, target, before, after)
            if blk is not None:
                # 同段同文献多点已由 build_window_block 合并为一个连续块
                contexts[target]["blocks"].append(blk)

    # 别名补齐：GROBID 漏打标记、但正文以方法名提及的文献
    for xml_id, aliases in (alias_map or {}).items():
        if xml_id not in refs_meta:
            continue
        if contexts[xml_id]["blocks"]:
            continue
        for elem in body.find_all(CONTEXT_CONTAINERS):
            raw = apply_noise_filters(
                "".join(_text_with_markers(*extract_paragraph_with_offsets(elem))))
            sentences = split_sentences_with_offsets(raw)
            low_all = raw.lower()
            alias = next((a for a in aliases if a.lower() in low_all), None)
            if not alias:
                continue
            si = next((i for i, (_, _, t) in enumerate(sentences)
                       if alias.lower() in t.lower()), None)
            if si is None:
                continue
            lo = max(0, si - before)
            hi = min(len(sentences) - 1, si + after)
            out_sents = []
            for j in range(lo, hi + 1):
                text = clean_context(sentences[j][2])
                if not text:
                    continue
                if j == si:
                    # 标出别名出现位置（别名不是 ref 标记，用 [[0]] 占位并写标签）
                    text = _wrap_first_alias(text, alias)
                    out_sents.append({"text": text, "cite": True,
                                      "markers": [{"pos": 0, "label": alias}]})
                else:
                    out_sents.append({"text": text, "cite": False, "markers": []})
            if out_sents:
                contexts[xml_id]["blocks"].append({"sentences": out_sents})
                contexts[xml_id]["count"] += 1
                break

    return {"refs_meta": refs_meta, "contexts": dict(contexts)}


# ------------------------------------------------------------- 并集 / 排序 / 简写

def fix_display_title(title, fixes):
    for bad, good in fixes:
        title = title.replace(bad, good)
    return title


def compute_rows(papers_data: dict, fixes: list) -> list:
    """跨论文并集（按归一化标题去重），行带稳定 ID。"""
    rows = {}
    for paper_key, data in papers_data.items():
        id2key = {}
        for xml_id, meta in data["refs_meta"].items():
            key = normalize_title(meta["title"])
            if is_garbage_title(meta["title"]):
                key = None
            id2key[xml_id] = key
            if key and key not in rows:
                rows[key] = {
                    "id": key,
                    "display_title": fix_display_title(meta["title"], fixes),
                    "year": meta["year"],
                    "per_paper": {},
                }
            elif key in rows and not rows[key]["year"] and meta["year"]:
                rows[key]["year"] = meta["year"]

        for xml_id, ctx in data["contexts"].items():
            key = id2key.get(xml_id)
            if not key:
                continue
            rows[key]["per_paper"][paper_key] = {
                "count": ctx["count"],
                "blocks": ctx["blocks"],
            }
    return list(rows.values())


def has_context(info) -> bool:
    """该篇是否在行里有可展示的上下文窗口。"""
    return bool(info and info.get("blocks"))


def iter_sentence_texts(info):
    """遍历某篇某行的所有句子文本（引用句含 [[k]] 占位符）。"""
    for blk in (info or {}).get("blocks", []):
        for s in blk["sentences"]:
            yield s["text"]


def row_total(row) -> int:
    """行总次数 = 各篇"有上下文句子"的提及次数之和（与表格展示口径一致）。"""
    return sum(i["count"] for i in row["per_paper"].values() if has_context(i))


def sort_rows(rows: list) -> list:
    """按总内部引用次数降序；并列时按标题字母序兜底（保证输出稳定）。"""
    return sorted(rows, key=lambda r: (-row_total(r), r["display_title"].lower()))


def rule_abbrev(title: str, rules: list) -> str:
    t = title.lower()
    for r in rules:
        if r["match"] in t:
            return r["abbr"]
    return ""


def auto_abbrev(title: str) -> str:
    """兜底启发式：方法论文标题多为 "NAME: 描述"，取冒号前的短词当简写。"""
    m = re.match(r"\s*([^:：]{1,60}?)\s*[:：]", title)
    if not m:
        return ""
    head = m.group(1).strip()
    if not head or not re.search(r"[A-Za-z]", head):
        return ""
    if len(head.split()) > 2:
        return ""
    if _disp_w(head) > 16:
        return ""
    return head


def abbrev_three_level(title: str, rules: list) -> tuple[str, str]:
    """返回 (简写, 来源)；来源 ∈ {"rule", "auto", ""}。"""
    a = rule_abbrev(title, rules)
    if a:
        return a, "rule"
    a = auto_abbrev(title)
    if a:
        return a, "auto"
    return "", ""


# ----------------------------------------------------------------- xlsx 渲染

def _disp_w(s):
    """显示宽度：CJK 全角算 2，其余算 1。"""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def _est_lines(text, col_width):
    """模拟 Excel 自动换行估算行数：CJK 逐字可断、拉丁按词断、超长词截断。"""
    if not text:
        return 1
    avail = max(4, int(col_width * 0.92))
    total = 0
    for hard in str(text).split("\n"):
        if not hard:
            total += 1
            continue
        tokens, buf = [], ""
        for c in hard:
            if unicodedata.east_asian_width(c) in "WF":
                if buf:
                    tokens.append(buf)
                    buf = ""
                tokens.append(c)
            else:
                buf += c
                if c == " ":
                    tokens.append(buf)
                    buf = ""
        if buf:
            tokens.append(buf)
        lines, cur = 1, 0
        for t in tokens:
            w = _disp_w(t)
            if cur + w <= avail:
                cur += w
                continue
            if w > avail:
                lines += 1 + (w - 1) // avail
                cur = w - ((w - 1) // avail) * avail
            else:
                lines += 1
                cur = w
        total += lines
    return total


LINE_PT = 15.0
PAD_PT = 6.0


def _fit_row_height(ws, row_idx, col_widths, min_height=22):
    max_lines = 1
    for cell in ws[row_idx]:
        v = cell.value
        if v is None or v == "":
            continue
        width = col_widths.get(cell.column_letter, 8.43)
        max_lines = max(max_lines, _est_lines(v, width))
    ws.row_dimensions[row_idx].height = max(min_height, max_lines * LINE_PT + PAD_PT)


MARK_RE = re.compile(r"\[\[(\d+)\]\]")


def render_sentence(text: str, markers: list, trans: dict) -> str:
    """渲染一句：命中译文则用中文，否则回退英文；再把 [[k]] 还原成 ⟦原文标记⟧。"""
    out = trans.get(_hash8(text), text)
    label_of = {m["pos"]: m["label"] for m in (markers or [])}
    out = MARK_RE.sub(lambda m: f"⟦{label_of.get(int(m.group(1)), '')}⟧", out)
    return re.sub(r"\s{2,}", " ", out).strip()


def render_block(block: dict, trans: dict) -> str:
    """把一个窗口块（多句）拼成一段：引用句前加 ▶。"""
    parts = []
    for s in block["sentences"]:
        text = render_sentence(s["text"], s.get("markers"), trans)
        if s.get("cite"):
            text = "▶ " + text
        parts.append(text)
    return " ".join(parts)


def render_xlsx(rows_sorted: list, project: dict) -> dict:
    """渲染终稿 xlsx（agentmemory_1 样式）。缺译句子回退显示英文原文。

    返回统计 {rows, missing_trans, rule_hits, auto_hits, no_abbrev, out_path}
    """
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font
    from openpyxl.utils import get_column_letter

    paper_order = project["paper_order"]
    headers = {k: v.get("header") or k.lower() for k, v in project["papers"].items()}
    trans = load_pool()
    rules = load_rules()

    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"

    header = [""]
    for pk in paper_order:
        header += [headers.get(pk, pk), COL_HEADER_COUNT]
    header += [COL_HEADER_TOTAL, COL_HEADER_ABBREV]
    ws.append(header)

    missing_trans, no_abbrev = [], []
    rule_hits = auto_hits = 0
    for r in rows_sorted:
        line = [r["display_title"]]
        total = 0
        for pk in paper_order:
            info = r["per_paper"].get(pk)
            if has_context(info):
                for s in iter_sentence_texts(info):
                    if _hash8(s) not in trans and s not in missing_trans:
                        missing_trans.append(s)
                cn = SENT_SEP.join(render_block(b, trans) for b in info["blocks"])
                line += [cn, info["count"]]
                total += info["count"]
            else:
                line += ["", ""]
        abbr, src = abbrev_three_level(r["display_title"], rules)
        if src == "rule":
            rule_hits += 1
        elif src == "auto":
            auto_hits += 1
        else:
            no_abbrev.append(r["display_title"])
        line += [total if total else "", abbr]
        ws.append(line)

    body_font = Font(name="宋体", size=11)
    wrap = Alignment(wrap_text=True, vertical="center")
    for row in ws.iter_rows():
        for cell in row:
            cell.font = body_font
            cell.alignment = wrap

    col_widths = {"A": 46}
    for i in range(len(paper_order)):
        c_ctx = 2 + i * 2
        col_widths[get_column_letter(c_ctx)] = 62
        col_widths[get_column_letter(c_ctx + 1)] = 13
    c_total = 2 + len(paper_order) * 2
    col_widths[get_column_letter(c_total)] = 12
    col_widths[get_column_letter(c_total + 1)] = 15
    for letter, w in col_widths.items():
        ws.column_dimensions[letter].width = w

    ws.freeze_panes = "B2"
    for row_idx in range(1, ws.max_row + 1):
        _fit_row_height(ws, row_idx, col_widths)

    wb.properties.creator = "Z.ai"
    out_path = ROOT / project.get("output_path", "data/exports/科研矩阵表_AgentMemory.xlsx")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        wb.save(out_path)
    except PermissionError:
        sys.exit(f"无法写入 {out_path} —— 请先关闭 Excel 里打开的矩阵表再重试")

    return {
        "rows": len(rows_sorted),
        "missing_trans": missing_trans,
        "rule_hits": rule_hits,
        "auto_hits": auto_hits,
        "no_abbrev": no_abbrev,
        "out_path": out_path,
    }


def print_render_summary(stats: dict):
    print(f"  行数: {stats['rows']} | 简写: 规则命中 {stats['rule_hits']}, "
          f"自动提取 {stats['auto_hits']}, 缺 {len(stats['no_abbrev'])}")
    if stats["missing_trans"]:
        print(f"  [缺译] {len(stats['missing_trans'])} 句先显示英文原文，"
              f"用 export-untranslated / import-translations 回填")
    if stats["no_abbrev"]:
        show = "；".join(t[:40] for t in stats["no_abbrev"][:5])
        more = " 等" if len(stats["no_abbrev"]) > 5 else ""
        print(f"  [缺简写] {len(stats['no_abbrev'])} 行（{show}{more}），"
              f"可在 data/config/abbrev_rules.json 增补规则")
    print(f"  已写出: {stats['out_path']}")


# ----------------------------------------------------------------- 配置/状态

def load_project() -> dict:
    p = CONFIG_DIR / "project.json"
    if not p.exists():
        sys.exit("未找到 data/config/project.json —— 请先运行: python matrix_tool.py init")
    proj = load_json(p)
    if proj.get("schema_version") != SCHEMA_VERSION:
        sys.exit(f"project.json schema_version 不兼容（{proj.get('schema_version')} != {SCHEMA_VERSION}）")
    return proj


def load_rules() -> list:
    return load_json(CONFIG_DIR / "abbrev_rules.json").get("rules", [])


def load_fixes() -> list:
    return [tuple(x) for x in load_json(CONFIG_DIR / "display_title_fixes.json").get("fixes", [])]


def load_alias_cfg() -> dict:
    return load_json(CONFIG_DIR / "alias_mentions.json").get("papers", {})


def load_translation_cfg(project: dict) -> dict:
    """读取自动翻译配置；缺项回落默认，未启用则返回 None。"""
    cfg = dict(DEFAULT_TRANSLATION)
    user = project.get("translation") or {}
    cfg.update({k: v for k, v in user.items() if v is not None})
    return cfg if cfg.get("enabled") else None


def load_window_cfg(project: dict, override: tuple | None = None) -> tuple:
    """读取上下文窗口 (before, after)；override 优先（来自 --window* 命令行）。"""
    if override is not None:
        before, after = override
    else:
        cw = project.get("context_window") or DEFAULT_CONTEXT_WINDOW
        before = cw.get("before", DEFAULT_CONTEXT_WINDOW["before"])
        after = cw.get("after", DEFAULT_CONTEXT_WINDOW["after"])
    try:
        before, after = int(before), int(after)
    except (TypeError, ValueError):
        before, after = DEFAULT_CONTEXT_WINDOW["before"], DEFAULT_CONTEXT_WINDOW["after"]
    return max(0, before), max(0, after)


def load_pool() -> dict:
    if not TRANS_POOL.exists():
        return {}
    d = load_json(TRANS_POOL)
    if "translations" in d and isinstance(d["translations"], dict):
        return d["translations"]
    return d  # 兼容旧的 flat 格式


def write_pool(pool: dict):
    write_json(TRANS_POOL, {"schema_version": SCHEMA_VERSION, "translations": pool})


def papers_data_fresh(project: dict, quiet: bool = True, window: tuple | None = None) -> dict:
    """从 TEI 缓存重新抽取全部种子论文（不依赖网络），TEI 是原始事实源。

    window: (before, after) 覆盖上下文窗口大小；None 时读 project.json 的 context_window。
    """
    alias_cfg = load_alias_cfg()
    win = load_window_cfg(project, window)
    papers_data = {}
    for key in project["paper_order"]:
        info = project["papers"].get(key)
        if info is None:
            sys.exit(f"project.json 的 paper_order 含未注册论文: {key}")
        tei = ROOT / info["tei"]
        if not tei.exists():
            sys.exit(f"缺少 TEI 缓存: {tei} —— 请重新 add 该论文（需 GROBID/VPN，或用 --from-tei）")
        papers_data[key] = extract_paper(key, tei.read_text(encoding="utf-8"),
                                         alias_cfg.get(key, {}), window=win)
        if not quiet:
            n = len(papers_data[key]["contexts"])
            print(f"  抽取 {key}: 参考文献 {len(papers_data[key]['refs_meta'])} 条, "
                              f"有上下文 {n} 条")
    return papers_data


# ----------------------------------------------------------------- 自动翻译（免费 MyMemory）

class TranslationQuotaError(Exception):
    """MyMemory 免费额度用尽（HTTP 429）。"""


def translate_via_mymemory(text: str, cfg: dict) -> str:
    """调用 MyMemory 公共接口把一句英文翻成中文。

    普通失败返回空串；免费额度用尽时抛 TranslationQuotaError（便于批量任务提前停止）。
    """
    import requests
    q = requests.utils.quote(text)
    url = (cfg["endpoint"].rstrip("/") + f"?q={q}"
           f"&langpair={cfg['source_lang']}|{cfg['target_lang']}")
    try:
        r = requests.get(url, timeout=cfg.get("timeout", 15))
        if r.status_code == 429:
            raise TranslationQuotaError(str(r.json().get("responseDetails", "quota")))
        r.raise_for_status()
        j = r.json()
        if str(j.get("responseStatus")) == "429" or "MYMEMORY WARNING" in str(j.get("responseDetails", "")):
            raise TranslationQuotaError(str(j.get("responseDetails", "quota")))
        if str(j.get("responseStatus")) != "200":
            return ""
        out = (j.get("responseData") or {}).get("translatedText", "")
        return out.strip() if isinstance(out, str) else ""
    except TranslationQuotaError:
        raise
    except Exception:
        return ""


def auto_translate_missing(rows: list, project: dict, quiet: bool = False) -> dict:
    """找出当前缺译句子并批量自动翻译，写回译文池（按内容哈希键）。

    返回统计 {translated, skipped, failed}；翻译失败/无配置/关闭时不中断出表。
    缺译句按去重后的集合处理，句子不变则哈希键不变，不会重复翻译同一句。
    """
    cfg = load_translation_cfg(project)
    if cfg is None:
        return {"translated": 0, "skipped": 0, "failed": 0, "quota_hit": False}

    pool = load_pool()
    missing = []
    seen = set()
    for r in rows:
        for info in r["per_paper"].values():
            for s in iter_sentence_texts(info):
                h = _hash8(s)
                if h not in pool and h not in seen:
                    seen.add(h)
                    missing.append((h, s))
    if not missing:
        if not quiet:
            print("  自动翻译: 无缺译句，跳过")
        return {"translated": 0, "skipped": 0, "failed": 0, "quota_hit": False}

    if not quiet:
        print(f"  自动翻译: 发现 {len(missing)} 句缺译，开始翻译 ...")
    limit = cfg.get("max_per_run", 500)
    translated = failed = 0
    quota_hit = False
    delay = cfg.get("delay", 0.2)
    for i, (h, s) in enumerate(missing):
        if i >= limit:
            break
        try:
            cn = translate_via_mymemory(s, cfg)
        except TranslationQuotaError as e:
            quota_hit = True
            if not quiet:
                print(f"  [自动翻译] 免费额度已用尽，剩余 {len(missing) - i} 句保留英文；"
                      f"额度恢复后跑 rebuild 自动续译")
                print(f"    （接口提示：{str(e)[:120]}）")
            break
        if cn and cn.lower() != s.lower():
            pool[h] = cn
            translated += 1
        else:
            failed += 1
        if delay:
            import time
            time.sleep(delay)
    if translated:
        write_pool(pool)
    skipped = max(0, len(missing) - limit)
    if not quiet:
        print(f"  自动翻译: 完成 {translated} 句, 失败 {failed} 句"
              + (f", 超出单次上限跳过 {skipped} 句" if skipped else "")
              + ("（额度用尽提前停止）" if quota_hit else ""))
    return {"translated": translated, "skipped": skipped, "failed": failed,
            "quota_hit": quota_hit}


def rebuild_all(project: dict, quiet: bool = False, no_translate: bool = False,
                window: tuple | None = None):
    """全量重建：重抽取全部论文 → 缓存单篇 JSON → 并集 → 排序 → 渲染 xlsx。

    no_translate=True 时跳过自动翻译缺译句（默认自动翻译）。
    window=(before, after) 覆盖上下文窗口；None 时读 project.json 的 context_window。
    """
    if not quiet:
        print("重新抽取全部种子论文 ...")
    papers_data = papers_data_fresh(project, quiet=quiet, window=window)
    for key, data in papers_data.items():
        write_json(PAPERS_STATE_DIR / f"{key}.json",
                   {"schema_version": PAPERS_SCHEMA_VERSION, "key": key,
                    "refs_meta": data["refs_meta"], "contexts": data["contexts"]})
    rows = sort_rows(compute_rows(papers_data, load_fixes()))
    if not no_translate:
        auto_translate_missing(rows, project, quiet=quiet)
    stats = render_xlsx(rows, project)
    if not quiet:
        print("全表重建完成:")
        print_render_summary(stats)
    return rows, stats


def rows_for_diff(project: dict) -> dict:
    rows = sort_rows(compute_rows(papers_data_fresh(project), load_fixes()))
    return {r["id"]: r for r in rows}


# ----------------------------------------------------------------- GROBID 客户端

def grobid_alive(base: str) -> bool:
    import requests
    r = requests.get(base.rstrip("/") + "/api/isalive", timeout=5)
    return r.text.strip().lower() == "true"


def grobid_fulltext(base: str, pdf_path: Path) -> str:
    import requests
    with open(pdf_path, "rb") as f:
        files = {"input": (pdf_path.name, f, "application/pdf")}
        r = requests.post(
            base.rstrip("/") + "/api/processFulltextDocument",
            files=files,
            data={"consolidateHeader": "1", "consolidateCitations": "0",
                  "includeRawCitations": "1"},
            timeout=600,
        )
    r.raise_for_status()
    return r.text


def parse_title_from_tei(tei_text: str) -> str:
    soup = BeautifulSoup(tei_text, "xml")
    t = soup.find("titleStmt")
    el = t.find("title") if t else None
    if el is None:
        el = soup.find("title")
    return el.get_text(" ", strip=True) if el else ""


# --------------------------------------------------------------------- 子命令

# init 用：现有 3 篇种子的迁移信息（TEI 为 2026-08-30 用 run_grobid_batch.py 生成）
LEGACY_SEEDS = {
    "HMARS": {
        "pdf": "data/seed_papers/HMARS_0603.pdf",
        "legacy_tei": "data/exports/seed_HMARS_0603_20260830_175456.tei.xml",
        "header": "hmars hierarchical multi-agent memory system for long-context reasoning",
        "added": "2026-08-30",
    },
    "MRAgent": {
        "pdf": "data/seed_papers/MRAgent.pdf",
        "legacy_tei": "data/exports/seed_MRAgent_20260830_180005.tei.xml",
        "header": "mragent memory is reconstructed not retrieved graph memory for llm agents",
        "added": "2026-08-30",
    },
    "PMA": {
        "pdf": "data/seed_papers/Proactive_Memory_Agent_0709.pdf",
        "legacy_tei": "data/exports/seed_Proactive_Memory_Agent_0709_20260830_180005.tei.xml",
        "header": "pma remember when it matters proactive memory agent for long-horizon agents",
        "added": "2026-08-30",
    },
}

DEFAULT_ABBREV_RULES = [
    {"match": "longbench v2", "abbr": "LongBench-v2"},
    {"match": "longbench", "abbr": "LongBench"},
    {"match": "τ 2", "abbr": "τ²-Bench"},
    {"match": "τ -bench", "abbr": "τ-Bench"},
    {"match": "a-mem", "abbr": "A-MEM"},
    {"match": "mem0 team", "abbr": "MEM0-Repo"},
    {"match": "mem0", "abbr": "MEM0"},
    {"match": "memgpt", "abbr": "MemGPT"},
    {"match": "memorybank", "abbr": "MemoryBank"},
    {"match": "evaluating very long-term conversational", "abbr": "LoCoMo"},
    {"match": "longmemeval", "abbr": "LongMemEval"},
    {"match": "a definition of agi", "abbr": "AGI"},
    {"match": "augmenting language models with long-term", "abbr": "LongMem"},
    {"match": "lost in the middle", "abbr": "LiTM"},
    {"match": "in prospect and retrospect", "abbr": "RMM"},
    {"match": "how to train your advisor", "abbr": "Advisor"},
    {"match": "learning knowledge graph world models", "abbr": "KGWM"},
    {"match": "hierarchical document refinement", "abbr": "HDR"},
    {"match": "retrieval-augmented generation for knowledge-intensive", "abbr": "RAG"},
    {"match": "a comprehensive survey of retrieval", "abbr": "RAG-Survey"},
    {"match": "agentic retrieval-augmented generation", "abbr": "AgenticRAG"},
    {"match": "retrieval-augmented generation with graphs", "abbr": "GraphRAG"},
    {"match": "from local to global", "abbr": "GraphRAG"},
    {"match": "graph rag", "abbr": "GraphRAG"},
    {"match": "voyager", "abbr": "Voyager"},
    {"match": "react", "abbr": "ReAct"},
    {"match": "reflexion", "abbr": "Reflexion"},
    {"match": "tree of thoughts", "abbr": "ToT"},
    {"match": "self-refine", "abbr": "Self-Refine"},
    {"match": "self-rag", "abbr": "Self-RAG"},
    {"match": "chain of agents", "abbr": "CoA"},
    {"match": "cocoa", "abbr": "CoCoA"},
    {"match": "memagent", "abbr": "MemAgent"},
    {"match": "memory os", "abbr": "MemoryOS"},
    {"match": "mem1", "abbr": "MEM1"},
    {"match": "himem", "abbr": "HiMem"},
    {"match": "h-mem", "abbr": "H-Mem"},
    {"match": "mem-α", "abbr": "Mem-α"},
    {"match": "temporal knowledge graph", "abbr": "Zep"},
    {"match": "langmem", "abbr": "LangMem"},
    {"match": "search-o1", "abbr": "Search-o1"},
    {"match": "search-r1", "abbr": "Search-R1"},
    {"match": "secom", "abbr": "SeCom"},
    {"match": "licomemory", "abbr": "Li-CoMemory"},
    {"match": "context-folding", "abbr": "Context-Folding"},
    {"match": "memory as action", "abbr": "Memory-as-Action"},
    {"match": "memory-r1", "abbr": "Memory-R1"},
    {"match": "mirix", "abbr": "MIRIX"},
    {"match": "lightmem", "abbr": "LightMem"},
    {"match": "raptor", "abbr": "RAPTOR"},
    {"match": "realm", "abbr": "REALM"},
    {"match": "realmem", "abbr": "RealMem"},
    {"match": "mle-bench", "abbr": "MLE-bench"},
    {"match": "terminal-bench", "abbr": "Terminal-Bench"},
    {"match": "seta", "abbr": "SETA"},
    {"match": "longagent", "abbr": "LongAgent"},
    {"match": "longrag", "abbr": "LongRAG"},
    {"match": "human-inspired reading agent", "abbr": "ReadAgent"},
    {"match": "claude api", "abbr": "Claude"},
    {"match": "gpt-5", "abbr": "GPT-5"},
    {"match": "generative agents", "abbr": "GenAgents"},
]

DEFAULT_ALIAS_MENTIONS = {
    "HMARS": {"b7": ["GraphRAG", "graph RAG"], "b15": ["GPT-5"],
              "b16": ["agentic RAG"], "b23": ["MemAgent"]},
    "MRAgent": {"b12": ["LangMem"]},
    "PMA": {"b8": ["Mem0"], "b18": ["Tree of Thoughts"], "b19": ["ReAct"]},
}

DEFAULT_TITLE_FIXES = [
    ["retrievalaugmented", "retrieval-augmented"],
    ["parametricretrieved", "parametric-retrieved"],
    ["memoryaugmented", "memory-augmented"],
]


def cmd_init(args):
    project_path = CONFIG_DIR / "project.json"
    if project_path.exists() and not args.force:
        sys.exit("data/config/project.json 已存在（如需重置请加 --force）")

    CONFIG_DIR.mkdir(exist_ok=True)
    PAPERS_STATE_DIR.mkdir(parents=True, exist_ok=True)

    write_json(CONFIG_DIR / "abbrev_rules.json",
               {"schema_version": SCHEMA_VERSION, "rules": DEFAULT_ABBREV_RULES})
    write_json(CONFIG_DIR / "alias_mentions.json",
               {"schema_version": SCHEMA_VERSION, "papers": DEFAULT_ALIAS_MENTIONS})
    write_json(CONFIG_DIR / "display_title_fixes.json",
               {"schema_version": SCHEMA_VERSION, "fixes": DEFAULT_TITLE_FIXES})

    papers = {}
    for key, s in LEGACY_SEEDS.items():
        dst = PAPERS_STATE_DIR / f"{key}.tei.xml"
        if dst.exists():
            print(f"TEI 缓存已存在，跳过复制: {key}")
        else:
            src = ROOT / s["legacy_tei"]
            if not src.exists():
                sys.exit(f"缺少 TEI（state 缓存与旧文件都没有）: {src}")
            shutil.copyfile(src, dst)
            print(f"已迁移 TEI: {key} <- {s['legacy_tei']}")
        papers[key] = {"pdf": s["pdf"], "tei": dst.relative_to(ROOT).as_posix(),
                       "header": s["header"], "added": s["added"]}

    legacy_pool = OUTPUT_DIR / "translations_by_hash.json"
    if TRANS_POOL.exists():
        print(f"译文池已存在，保留现池 {len(load_pool())} 条")
    elif legacy_pool.exists():
        old = load_json(legacy_pool)
        write_pool(old.get("translations", old) if isinstance(old, dict) else {})
        print(f"已迁移译文池: {len(load_pool())} 条 <- {legacy_pool.name}")
    else:
        write_pool({})
        print("[warn] 找不到任何译文池，从空开始")

    project = {
        "schema_version": SCHEMA_VERSION,
        "grobid_url": "http://localhost:8070",
        "output_path": "data/exports/科研矩阵表_AgentMemory.xlsx",
        "paper_order": list(LEGACY_SEEDS.keys()),
        "papers": papers,
        "translation": dict(DEFAULT_TRANSLATION),
        "context_window": dict(DEFAULT_CONTEXT_WINDOW),
    }
    write_json(project_path, project)
    print("配置已生成: data/config/{project,abbrev_rules,alias_mentions,display_title_fixes}.json\n")

    rows, stats = rebuild_all(project, quiet=True)
    ok = self_check(rows)
    print()
    print_render_summary(stats)
    if not ok:
        sys.exit("[FAIL] 对账未通过，请检查上方差异")
    print("\ninit 完成。以后加新种子论文: python matrix_tool.py add 新论文.pdf")


def self_check(rows_sorted: list) -> bool:
    """对账：与迁移前的 data/exports/matrix_data.json 逐行比对（内容应完全一致，仅排序不同）。"""
    legacy = OUTPUT_DIR / "matrix_data.json"
    if not legacy.exists():
        print("[self-check] 找不到 data/exports/matrix_data.json，跳过对账")
        return True
    old_rows = load_json(legacy)
    new_by_id = {r["id"]: r for r in rows_sorted}
    old_ids = {normalize_title(o["display_title"]) for o in old_rows}

    problems = []
    for o in old_rows:
        rid = normalize_title(o["display_title"])
        n = new_by_id.get(rid)
        if n is None:
            problems.append(f"缺行: {o['display_title'][:50]}")
            continue
        if n["display_title"] != o["display_title"]:
            problems.append(f"标题不同: {o['display_title'][:40]!r} -> {n['display_title'][:40]!r}")
        if (n["year"] or "") != (o.get("year") or ""):
            problems.append(f"年份不同: {o['display_title'][:40]}: {o.get('year')!r} -> {n['year']!r}")
        opk, npk = o.get("per_paper") or {}, n["per_paper"]
        if set(opk) != set(npk):
            problems.append(f"论文列不同: {o['display_title'][:40]}: {sorted(opk)} -> {sorted(npk)}")
            continue
        for pk in opk:
            if opk[pk]["count"] != npk[pk]["count"]:
                problems.append(f"次数不同: {o['display_title'][:40]} [{pk}]: "
                                f"{opk[pk]['count']} -> {npk[pk]['count']}")
            # 结构升级后旧文件存的是平铺 sentences、新表存 blocks；仅在两者格式一致时比对
            if "sentences" in opk[pk] and "sentences" in npk[pk] \
                    and opk[pk]["sentences"] != npk[pk]["sentences"]:
                problems.append(f"句子不同: {o['display_title'][:40]} [{pk}]")
    extra = sorted(new_by_id.keys() - old_ids)
    for rid in extra:
        problems.append(f"多行: {new_by_id[rid]['display_title'][:50]}")

    totals = [row_total(r) for r in rows_sorted]
    desc_ok = all(a >= b for a, b in zip(totals, totals[1:]))

    print(f"\n自检对账: 旧 matrix_data.json {len(old_rows)} 行 vs 新表 {len(rows_sorted)} 行")
    if problems:
        for p in problems[:8]:
            print("  [diff]", p)
        if len(problems) > 8:
            print(f"  ... 共 {len(problems)} 处差异")
    else:
        print("  行集合/标题/年份/各篇次数/上下文句子 全部一致 ✓（仅行排序不同）")
    print(f"  排序校验: 总内部引用次数非递增 {'✓' if desc_ok else '✗'}")
    return not problems and len(old_rows) == len(rows_sorted) and desc_ok


def _resolve_key(project: dict, pdf: Path | None, key_arg: str | None) -> str:
    if key_arg:
        return re.sub(r"[^A-Za-z0-9_\-]+", "_", key_arg.strip())
    stem = pdf.stem if pdf else "PAPER"
    return re.sub(r"[^A-Za-z0-9_\-]+", "_", stem) or "PAPER"


def _cli_window(args):
    """把命令行 --window / --window-before / --window-after 解析为 (before, after)。

    都没给时返回 None（由 data/config/project.json 的 context_window 决定）。
    --window N 等价于前后各 N；--window-before/--window-after 单独覆盖对应方向。
    """
    w = getattr(args, "window", None)
    wb = getattr(args, "window_before", None)
    wa = getattr(args, "window_after", None)
    if w is None and wb is None and wa is None:
        return None
    base = w if w is not None else 0
    before = wb if wb is not None else base
    after = wa if wa is not None else base
    return max(0, int(before)), max(0, int(after))


def cmd_add(args):
    project = load_project()

    pdf_abs = None
    if args.pdf:
        pdf_abs = Path(args.pdf).expanduser()
        if not pdf_abs.exists():
            pdf_abs = ROOT / args.pdf
        if not pdf_abs.exists():
            sys.exit(f"找不到 PDF: {args.pdf}")
        pdf_abs = pdf_abs.resolve()

    key = _resolve_key(project, pdf_abs, args.key)
    if key in project["papers"] and not args.force:
        sys.exit(f"种子论文 {key} 已存在（重新解析请加 --force；删除用 remove {key}）")

    before = rows_for_diff(project)

    # 取 TEI：离线入口或 GROBID 解析
    if args.from_tei:
        tei_src = Path(args.from_tei).expanduser()
        if not tei_src.exists():
            tei_src = ROOT / args.from_tei
        if not tei_src.exists():
            sys.exit(f"找不到 TEI 文件: {args.from_tei}")
        tei_text = tei_src.read_text(encoding="utf-8")
        print(f"使用现成 TEI: {tei_src}")
    else:
        base = project.get("grobid_url", "")
        try:
            alive = grobid_alive(base)
        except Exception as e:
            alive = False
            print(f"[warn] GROBID 连接失败: {e}")
        if not alive:
            sys.exit(f"GROBID 不可达（{base}）—— 请先连接校园 VPN 后重试，"
                     f"或改用 --from-tei 离线入口")
        print(f"GROBID 解析中（约需 1-2 分钟）: {pdf_abs.name} ...")
        tei_text = grobid_fulltext(base, pdf_abs)

    # PDF 归位到 data/seed_papers（--from-tei 可不带 PDF）
    if pdf_abs is not None:
        INPUT_SEED_DIR.mkdir(parents=True, exist_ok=True)
        if pdf_abs.parent != INPUT_SEED_DIR:
            shutil.copyfile(pdf_abs, INPUT_SEED_DIR / pdf_abs.name)
            pdf_abs = INPUT_SEED_DIR / pdf_abs
        pdf_rel = pdf_abs.relative_to(ROOT).as_posix()
    else:
        pdf_rel = ""

    tei_rel = (PAPERS_STATE_DIR / f"{key}.tei.xml").relative_to(ROOT).as_posix()
    _atomic_write_text(ROOT / tei_rel, tei_text)

    title = parse_title_from_tei(tei_text)
    header = title.lower() if title else key.lower()
    project["papers"][key] = {
        "pdf": pdf_rel,
        "tei": tei_rel,
        "header": header,
        "added": _beijing_date(),
    }
    if key not in project["paper_order"]:
        project["paper_order"].append(key)
    write_json(CONFIG_DIR / "project.json", project)

    alias_cfg = load_alias_cfg()
    win = load_window_cfg(project, _cli_window(args))
    data = extract_paper(key, tei_text, alias_cfg.get(key, {}), window=win)
    write_json(PAPERS_STATE_DIR / f"{key}.json",
               {"schema_version": PAPERS_SCHEMA_VERSION, "key": key,
                "refs_meta": data["refs_meta"], "contexts": data["contexts"]})

    print(f"已注册种子论文 {key}: 参考文献 {len(data['refs_meta'])} 条, "
          f"有上下文 {len(data['contexts'])} 条, 表头 = {header[:60]!r}")

    rows, stats = rebuild_all(project, quiet=True, no_translate=args.no_translate, window=win)

    after = {r["id"]: r for r in rows}
    added = [i for i in after if i not in before]
    updated = [i for i in after
               if i in before and after[i]["per_paper"] != before[i]["per_paper"]]
    print(f"\n表格重建: {stats['rows']} 行（新增 {len(added)} 行, "
          f"更新 {len(updated)} 行）")
    for rid in added[:5]:
        print(f"  + {after[rid]['display_title'][:60]}")

    n_new_missing = 0
    if stats["missing_trans"]:
        before_sents = {s for r in before.values()
                        for i in r["per_paper"].values() for s in iter_sentence_texts(i)}
        n_new_missing = sum(1 for s in stats["missing_trans"] if s not in before_sents)
    if stats["missing_trans"]:
        path_txt, path_json = export_untranslated(project, quiet=True)
        print(f"  缺译 {len(stats['missing_trans'])} 句（其中新增 {n_new_missing} 句）"
              f" -> {path_txt.name} / {path_json.name}")
    else:
        print("  缺译 0 句")
    print_render_summary(stats)


def export_untranslated(project: dict, quiet: bool = False):
    """把缺译句子写成 {hash: 英文句} JSON（把值改成中文即可 import 回填）+ 可读 txt。"""
    rows = sort_rows(compute_rows(papers_data_fresh(project), load_fixes()))
    trans = load_pool()
    missing = []
    for r in rows:
        for info in r["per_paper"].values():
            for s in iter_sentence_texts(info):
                if _hash8(s) not in trans and s not in missing:
                    missing.append(s)
    if not missing:
        if not quiet:
            print("全部句子均已翻译，无需导出")
        return None, None
    ts = now_beijing_iso_no_tz()
    txt_path = OUTPUT_DIR / f"untranslated_{ts}.txt"
    json_path = OUTPUT_DIR / f"untranslated_{ts}.json"
    txt_path.write_text(
        "\n".join(f"[{i}] {s}" for i, s in enumerate(missing)) + "\n",
        encoding="utf-8", newline="\n")
    write_json(json_path, {_hash8(s): s for s in missing})
    if not quiet:
        print(f"导出缺译 {len(missing)} 句:\n  {txt_path}\n  {json_path}\n"
              f"翻译后: 把 json 里的英文值改成中文译文（键不动），"
              f"然后 import-translations {json_path.name}")
    return txt_path, json_path


def cmd_export(args):
    export_untranslated(load_project())


def cmd_import(args):
    src = Path(args.file).expanduser()
    if not src.exists():
        src = ROOT / args.file
    if not src.exists():
        sys.exit(f"找不到文件: {args.file}")
    data = load_json(src)
    if isinstance(data, dict) and isinstance(data.get("translations"), dict):
        data = data["translations"]

    pool = load_pool()
    added = updated = skipped = 0
    for k, v in data.items():
        if not isinstance(v, str) or not v.strip():
            skipped += 1
            continue
        h = k.strip() if re.fullmatch(r"[0-9a-f]{8}", k.strip()) else _hash8(k.strip())
        v = v.strip()
        if h in pool:
            if pool[h] == v:
                continue
            updated += 1
        else:
            added += 1
        pool[h] = v
    write_pool(pool)
    print(f"译文池合并完成: 新增 {added} 条, 更新 {updated} 条, "
          f"跳过 {skipped} 条, 现共 {len(pool)} 条")
    rebuild_all(load_project())


def cmd_rebuild(args):
    project = load_project()
    rebuild_all(project, no_translate=args.no_translate, window=_cli_window(args))


def cmd_remove(args):
    project = load_project()
    key = args.key
    if key not in project["papers"]:
        sys.exit(f"未注册的种子论文: {key}（现有: {', '.join(project['paper_order'])}）")
    del project["papers"][key]
    project["paper_order"].remove(key)
    write_json(CONFIG_DIR / "project.json", project)
    for suffix in (".tei.xml", ".json"):
        p = PAPERS_STATE_DIR / f"{key}{suffix}"
        p.unlink(missing_ok=True)
    print(f"已注销种子论文 {key} 并删除其状态文件")
    rebuild_all(project)


def cmd_status(args):
    project = load_project()
    print(f"输出文件: {project.get('output_path')} | GROBID: {project.get('grobid_url')}")
    print(f"种子论文 {len(project['paper_order'])} 篇:")
    for key in project["paper_order"]:
        info = project["papers"][key]
        print(f"  {key:<12} 加入 {info.get('added', '?')}  表头: {info.get('header', '')[:58]}")

    rows = sort_rows(compute_rows(papers_data_fresh(project), load_fixes()))
    trans = load_pool()
    rules = load_rules()
    n_missing = sum(1 for r in rows for info in r["per_paper"].values()
                    for s in iter_sentence_texts(info)
                    if _hash8(s) not in trans)  # 按出现次计，未去重
    uniq_missing = {s for r in rows for info in r["per_paper"].values()
                    for s in iter_sentence_texts(info) if _hash8(s) not in trans}
    no_abbrev = [r["display_title"] for r in rows if not abbrev_three_level(r["display_title"], rules)[0]]
    n_ctx = sum(1 for r in rows if r["per_paper"])
    print(f"\n当前表格: {len(rows)} 行（有上下文 {n_ctx} 行）| "
          f"缺译 {len(uniq_missing)} 句 | 缺简写 {len(no_abbrev)} 行")
    if no_abbrev:
        print("  缺简写行（可在 data/config/abbrev_rules.json 增补）:")
        for t in no_abbrev[:10]:
            print(f"    - {t[:60]}")
        if len(no_abbrev) > 10:
            print(f"    ... 共 {len(no_abbrev)} 行")
    top = rows[0] if rows else None
    if top:
        print(f"当前最高被引: {top['display_title'][:50]} "
              f"（总内部引用 {row_total(top)} 次）")


# ------------------------------------------------------------- 项目专属 help（中文）
# 与 main() 里的子命令注册同源；加新命令时同步在此登记，离线可用、不读 README/AGENTS。
COMMANDS_HELP = {
    "init": {
        "usage": "matrix_tool.py init [--force]",
        "desc": "一次性迁移：生成 4 个 config、复制已有 TEI/译文池进 state，逐篇抽取并重建 xlsx，最后自检对账。",
        "args": [
            "--force    覆盖已有配置重新初始化（会优先复用 data/state 里已有的 TEI 和译文池）",
        ],
        "example": "matrix_tool.py init",
        "notes": "仅首次或想整体重置时使用；日常加论文用 add，改完配置用 rebuild。",
    },
    "add": {
        "usage": "matrix_tool.py add 新论文.pdf [--key KEY] [--force] [--from-tei 现成.tei.xml] [--no-translate] [--window N]",
        "desc": "加一篇新种子论文：GROBID 解析（或 --from-tei 离线）→ 注册 → 抽取 → 重建 → 自动翻译缺译句。",
        "args": [
            "pdf            种子论文 PDF（--from-tei 时可省略）",
            "--key KEY      论文短名（默认取 PDF 文件名）",
            "--force        key 已存在时强制重新解析覆盖",
            "--from-tei     离线入口：直接使用现成 TEI XML，跳过 GROBID",
            "--no-translate 跳过自动翻译缺译句（默认自动翻译）",
            "--window N     上下文窗口：前后各 N 句（0=只显示引用句）",
            "--window-before / --window-after  分别指定前后句数",
        ],
        "example": "matrix_tool.py add data/seed_papers/新论文.pdf",
        "notes": "需连校园 VPN 使 GROBID 可达；无 VPN 可用 --from-tei 加论文 / 冒烟测试。",
    },
    "rebuild": {
        "usage": "matrix_tool.py rebuild [--no-translate] [--window N] [--window-before N] [--window-after N]",
        "desc": "全量重建：从 TEI 重新抽取全部论文 → 上下文窗口 → 并集 → 按总次数降序 → 回填译文 → 写 xlsx；同时自动补齐缺译句。",
        "args": [
            "--no-translate 跳过自动翻译缺译句（默认自动翻译）",
            "--window N     上下文窗口：前后各 N 句（覆盖 config，0=只显示引用句）",
            "--window-before / --window-after  分别指定前后句数",
        ],
        "example": "matrix_tool.py rebuild",
        "notes": "改过任何 data/config/*.json 或译文后跑它；xlsx 只是导出物，永远不要手改。",
    },
    "export-untranslated": {
        "usage": "matrix_tool.py export-untranslated",
        "desc": "导出缺译句子清单：data/exports/untranslated_<时间戳>.txt（可读版）+ 同名 .json（含 8 位 hash，便于回填）。",
        "args": [],
        "example": "matrix_tool.py export-untranslated",
        "notes": "通常无需手动翻译（add/rebuild 已自动翻）；仅在你想人工精修某句译文时用。",
    },
    "import-translations": {
        "usage": "matrix_tool.py import-translations 文件.json",
        "desc": "把译文合并进译文池（接受 {hash: 中文} 或 {英文原句: 中文}），并自动 rebuild 回填。",
        "args": [
            "file  译文 JSON：{hash: 中文} 或 {英文原句: 中文}（键不动，值改成中文）",
        ],
        "example": "matrix_tool.py import-translations data/exports/untranslated_20260905_123634.json",
        "notes": "用于人工精修/校对：把 export 的 json 里英文值改成中文，键（8 位 hash）保持不变。",
    },
    "remove": {
        "usage": "matrix_tool.py remove KEY",
        "desc": "注销某篇种子论文（删其状态文件）并重建——加错了用来纠正。",
        "args": [
            "KEY  要注销的种子论文短名（见 status 列表）",
        ],
        "example": "matrix_tool.py remove TEST",
        "notes": "仅删除该篇的 TEI/JSON 状态文件，不动译文池与其他论文。",
    },
    "status": {
        "usage": "matrix_tool.py status",
        "desc": "查看现状：种子论文列表、当前行数、缺译句数、缺简写行清单、最高被引。",
        "args": [],
        "example": "matrix_tool.py status",
        "notes": "改动任何 .py、data/config 或 data/state 后跑一次，确认无回归。",
    },
}


def cmd_help(args):
    """项目专属中文帮助。无参：列出所有命令；带 cmd：展开单个命令详解。"""
    if not args.cmd:
        print("可用命令：")
        for name, info in COMMANDS_HELP.items():
            print(f"  {name:<24}{info['desc']}")
        print(f"\n想看某命令的用法/参数/示例：matrix_tool.py help 命令名")
        return

    name = args.cmd
    info = COMMANDS_HELP.get(name)
    if info is None:
        available = "、".join(COMMANDS_HELP)
        print(f"未知命令：{name!r}")
        print(f"可用命令：{available}")
        sys.exit(1)

    print(f"命令：{name}")
    print(f"用途：{info['desc']}")
    print(f"用法：{info['usage']}")
    if info["args"]:
        print("参数：")
        for a in info["args"]:
            print(f"  {a}")
    print(f"示例：{info['example']}")
    if info["notes"]:
        print(f"注意：{info['notes']}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="matrix_tool.py", description="科研矩阵表生长工具")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="首次迁移现有 3 篇种子并自检对账")
    p.add_argument("--force", action="store_true", help="覆盖已有配置重新初始化")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("add", help="添加一篇种子论文并重建表格")
    p.add_argument("pdf", nargs="?", help="种子论文 PDF（--from-tei 时可省略）")
    p.add_argument("--key", help="论文短名（默认取 PDF 文件名）")
    p.add_argument("--force", action="store_true", help="key 已存在时强制重新解析覆盖")
    p.add_argument("--from-tei", dest="from_tei", help="离线入口：直接使用现成 TEI XML")
    p.add_argument("--no-translate", action="store_true",
                   help="跳过自动翻译缺译句（默认自动翻译）")
    p.add_argument("--window", type=int, help="上下文窗口：前后各 N 句（覆盖 config，0=只显示引用句）")
    p.add_argument("--window-before", type=int, dest="window_before", help="引用句前 N 句")
    p.add_argument("--window-after", type=int, dest="window_after", help="引用句后 N 句")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("rebuild", help="全量重建表格（改过 data/config 或译文后运行）")
    p.add_argument("--no-translate", action="store_true",
                   help="跳过自动翻译缺译句（默认自动翻译）")
    p.add_argument("--window", type=int, help="上下文窗口：前后各 N 句（覆盖 config，0=只显示引用句）")
    p.add_argument("--window-before", type=int, dest="window_before", help="引用句前 N 句")
    p.add_argument("--window-after", type=int, dest="window_after", help="引用句后 N 句")
    p.set_defaults(func=cmd_rebuild)

    p = sub.add_parser("export-untranslated", help="导出缺译句子清单")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("import-translations", help="回填译文并重建")
    p.add_argument("file", help="译文 JSON：{hash: 中文} 或 {英文原句: 中文}")
    p.set_defaults(func=cmd_import)

    p = sub.add_parser("remove", help="注销某篇种子论文并重建")
    p.add_argument("key")
    p.set_defaults(func=cmd_remove)

    p = sub.add_parser("status", help="查看种子论文与表格现状")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("help", help="项目专属中文帮助（help 或 help 命令名）")
    p.add_argument("cmd", nargs="?", help="要查看的某个命令名（省略则列出全部命令）")
    p.set_defaults(func=cmd_help)

    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    args = parser.parse_args(argv)
    logger = _setup_logging(args.cmd)
    started = time.perf_counter()
    _log_event(logger, "command_started", command=args.cmd, argv=raw_argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    try:
        args.func(args)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        _log_event(
            logger,
            "command_finished",
            command=args.cmd,
            status="failed",
            exit_code=code,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            message=str(exc) if exc.code is not None else "",
        )
        raise
    except BaseException as exc:
        _log_event(
            logger,
            "command_finished",
            command=args.cmd,
            status="error",
            exit_code=1,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            error_type=type(exc).__name__,
            message=str(exc),
            traceback=traceback.format_exc(),
        )
        raise
    else:
        _log_event(
            logger,
            "command_finished",
            command=args.cmd,
            status="success",
            exit_code=0,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )


if __name__ == "__main__":
    main()
