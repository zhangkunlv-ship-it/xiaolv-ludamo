#!/usr/bin/env python3
"""判断台的账本：记事实、记原话、记问过什么。

存在本机，不进任何仓库。

  recall    开场：把账翻出来
  echo      开场：直接给三句能说出口的话
  remember  记一条（只记他亲口说的）
  ask       问过没有 / 登记 / 补记回答
  stat      数一数
  pack      打一个不含任何人数据的包
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from collections import OrderedDict
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TPL = ROOT / "users" / "_template"
STORE = Path(os.environ.get("LUDAMO_HOME") or (Path.home() / ".xiaolv-ludamo")) / "memory"
STALE_DAYS = 30

# kind -> PROFILE.md 里的段落名
FIELDS = OrderedDict([
    ("biz",      "身份与业务"),
    ("num",      "关键数字"),
    ("quote",    "用户原话"),
    ("voice",    "语言指纹"),
    ("promise",  "上次行动承诺"),
    ("conflict", "待澄清冲突"),
    ("act",      "已确认的事实"),
])
TAIL = "废止链"
KINDS = list(FIELDS) + ["correction"]
SHOW_ORDER = list(FIELDS.values()) + [TAIL]

DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
FLOW_RE = re.compile(r"^## (\d{4}-\d{2}-\d{2}) \| (\S+) \| (.+)$")


# ---------------------------------------------------------------- 路径
def home(uid: str) -> Path:
    return STORE / "users" / uid


def init(uid: str) -> Path:
    d = home(uid)
    d.mkdir(parents=True, exist_ok=True)
    for fn in ("PROFILE.md", "TIMELINE.md"):
        target = d / fn
        if target.exists():
            continue
        seed = TPL / fn
        if not seed.exists():
            target.write_text(f"# {fn}\n", encoding="utf-8")
            continue
        kept = [ln for ln in seed.read_text(encoding="utf-8").splitlines()
                if not _placeholder(ln) and "模板示例" not in ln]
        target.write_text("\n".join(kept) + "\n", encoding="utf-8")
    if asks_file(d).name != "asks.json":
        pass
    if not (d / "asks.json").exists():
        legacy = d / "asked.json"
        if legacy.exists():
            try:
                old = json.loads(legacy.read_text(encoding="utf-8")).get("questions", [])
                conv = [{"ask": x.get("q", ""), "kind": x.get("type", ""),
                         "ts": x.get("at", ""), "reply": x.get("answer", "")} for x in old]
                (d / "asks.json").write_text(json.dumps({"asks": conv}, ensure_ascii=False, indent=2),
                                             encoding="utf-8")
                legacy.unlink()
            except Exception:
                (d / "asks.json").write_text('{"asks": []}', encoding="utf-8")
        else:
            (d / "asks.json").write_text('{"asks": []}', encoding="utf-8")
    return d


def asks_file(d: Path) -> Path:
    return d / "asks.json"


def _placeholder(line: str) -> bool:
    t = line.strip()
    return t.startswith("- [ ]") or t.startswith("- [旧值]")


# ---------------------------------------------------------------- 解析
def blocks(path: Path) -> dict:
    """PROFILE.md -> {段名: [原始行]}"""
    out: dict[str, list[str]] = {}
    cur = None
    for ln in path.read_text(encoding="utf-8").splitlines():
        if ln.startswith("## "):
            cur = ln[3:].strip()
            out.setdefault(cur, [])
        elif cur is not None and ln.strip() and not ln.startswith(">"):
            out[cur].append(ln.rstrip())
    return out


def items(lines: list[str]) -> list[str]:
    """只留真正记下的条目。"""
    got = []
    for ln in lines:
        t = ln.strip()
        if not t.startswith("-") or _placeholder(ln) or t.startswith("-（") or t.startswith("- （"):
            continue
        got.append(t.lstrip("- ").strip())
    return got


def insert(path: Path, section: str, entry: str) -> None:
    src = path.read_text(encoding="utf-8").splitlines()
    head = f"## {section}"
    idx = next((i for i, ln in enumerate(src) if ln.startswith(head)), None)
    if idx is None:
        path.write_text(path.read_text(encoding="utf-8").rstrip("\n")
                        + f"\n\n## {section}\n{entry}\n", encoding="utf-8")
        return
    end = next((i for i in range(idx + 1, len(src)) if src[i].startswith("## ")), len(src))
    while end > idx + 1 and not src[end - 1].strip():
        end -= 1
    body = [ln for ln in src[idx + 1:end] if ln.strip() and not ln.strip().startswith("（")]
    if not body or all(_placeholder(ln) for ln in body):
        src[idx + 1:end] = [entry]
    else:
        src.insert(end, entry)
    path.write_text("\n".join(src) + "\n", encoding="utf-8")


def log(d: Path, kind: str, text: str, day: str) -> None:
    with (d / "TIMELINE.md").open("a", encoding="utf-8") as f:
        f.write(f"\n## {day} | {kind} | {text}\n")


def flow(d: Path) -> list[str]:
    out = []
    for ln in (d / "TIMELINE.md").read_text(encoding="utf-8").splitlines():
        if FLOW_RE.match(ln):
            out.append(ln)
    return out


def load_asks(d: Path) -> list[dict]:
    f = asks_file(d)
    if not f.exists():
        return []
    try:
        return json.loads(f.read_text(encoding="utf-8")).get("asks", [])
    except Exception:
        return []


def save_asks(d: Path, rows: list[dict]) -> None:
    asks_file(d).write_text(json.dumps({"asks": rows}, ensure_ascii=False, indent=2), encoding="utf-8")


def key(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def stale_old(blk: dict) -> list[str]:
    """关键数字里超过 30 天、且还没进废止链的。"""
    dead = " ;; ".join(items(blk.get(TAIL, [])))
    today = date.today()
    out = []
    for raw in blk.get("关键数字", []):
        clean = items([raw])
        if not clean:
            continue
        m = DATE_RE.search(clean[0])
        if not m:
            continue
        try:
            old = (today - datetime.strptime(m.group(1), "%Y-%m-%d").date()).days > STALE_DAYS
        except ValueError:
            continue
        if old and clean[0].split("（")[0] not in dead:
            out.append(clean[0])
    return out


# ---------------------------------------------------------------- 命令
def do_recall(a) -> None:
    d = home(a.user)
    if not d.exists():
        print("[账本] 空。当第一次见，别提早前的事。")
        return
    blk = blocks(d / "PROFILE.md")
    print("=== 账本 ===")
    any_ = False
    for name in SHOW_ORDER:
        vals = items(blk.get(name, []))
        if not vals:
            continue
        any_ = True
        print(f"[{name}]")
        for v in vals[-6:]:
            print(f"  {v}")
    if not any_:
        print("（有空壳，没有内容）")

    old = stale_old(blk)
    if old:
        print("[过 30 天 · 开场要先钉一次]")
        for v in old[-5:]:
            print(f"  {v}")

    open_q = [r for r in load_asks(d) if not r.get("reply")]
    if open_q:
        print("[问过没答 · 别换说法重问]")
        for r in open_q[-6:]:
            print(f"  - {r.get('ask','')}")

    f = flow(d)
    if f:
        print("[最近的事]")
        for ln in f[-8:]:
            print(f"  {ln}")
    print("=== 完 ===")
    print(f"（{d}）")


def do_echo(a) -> None:
    """直接给三句能说出口的话。"""
    d = home(a.user)
    if not d.exists():
        print("[开场] 空账本，正常开场。")
        return
    blk = blocks(d / "PROFILE.md")
    print("=== 开场素材（照着说，别念出来） ===")
    hit = False

    ps = items(blk.get("上次行动承诺", []))
    if ps:
        hit = True
        print("① 接上次：")
        print(f"   {ps[-1]}")
        print("   → 说成：上次你说要去做的这件。做到哪一步了。")

    old = stale_old(blk)
    if old:
        hit = True
        print("② 钉旧数（已经过期，先用它压住）：")
        print(f"   {old[-1]}")
        print("   → 说成：这个数是一个月前的。现在呢。")

    un = [r for r in load_asks(d) if not r.get("reply")]
    if un:
        hit = True
        print("③ 接没答的问题（别换说法）：")
        print(f"   {un[-1].get('ask','')}")

    qs = items(blk.get("用户原话", []))
    if qs:
        hit = True
        print("④ 能还回去的原话：")
        for q in qs[-2:]:
            print(f"   {q}")
        print("   → 说成：你上次是这句。这次是另一句。哪句算数。")

    vs = items(blk.get("语言指纹", []))
    if vs:
        hit = True
        print("⑤ 他糊事的习惯（决定你怎么问）：")
        print(f"   {vs[-1]}")

    if not hit:
        print("（没有可用素材，正常开场）")
    print("=== 完 ===")


def do_remember(a) -> None:
    if a.kind not in KINDS:
        sys.exit(f"kind 只能是 {KINDS}")
    d = init(a.user)
    day = a.date or date.today().isoformat()
    txt = a.text.strip()
    prof = d / "PROFILE.md"

    if a.kind == "correction" or a.correction_of:
        old = a.correction_of or "(未写旧值)"
        log(d, "correction", f"改口：{old} → {txt}", day)
        insert(prof, TAIL, f"- {old} → 更正于 {day} → 新值：{txt}")
        print(f"[记] 改口入废止链：{old} → {txt}")
        return

    sec = FIELDS[a.kind]
    if a.kind in ("num", "promise"):
        line = f"- {txt}（{day}）"
    elif a.kind == "quote":
        line = f"- 「{txt}」（{day}）"
    else:
        line = f"- {txt}"

    log(d, a.kind, txt, day)
    insert(prof, sec, line)
    print(f"[记] {a.kind} → [{sec}]：{txt}")


def do_ask(a) -> None:
    d = init(a.user)
    if not (a.check or a.log):
        sys.exit("要 --check 或 --log")
    rows = load_asks(d)

    if a.check:
        k = key(a.check)
        same = [r for r in rows if key(r.get("ask")) == k]
        print(json.dumps({
            "duplicate": bool(same),
            "last_reply": (same[-1].get("reply") or None) if same else None,
            "asked_total": len(rows),
        }, ensure_ascii=False))
        return

    k = key(a.log)
    for r in rows:
        if key(r.get("ask")) == k:
            if a.answer:
                r["reply"] = a.answer
                r["reply_ts"] = date.today().isoformat()
                save_asks(d, rows)
                print(f"[问] 补记回答：{a.log} → {a.answer}")
                return
            print(f"[问] 已经问过，不重复登记：{a.log}")
            return

    rows.append({"ask": a.log, "kind": a.type or "", "ts": date.today().isoformat(),
                 "reply": a.answer or ""})
    save_asks(d, rows)
    print(f"[问] 登记（累计 {len(rows)} 条）：{a.log}")


def do_stat(a) -> None:
    d = home(a.user)
    if not d.exists():
        print("[数] 空。")
        return
    blk = blocks(d / "PROFILE.md")
    print(f"[数] {d}")
    for name in SHOW_ORDER:
        n = len(items(blk.get(name, [])))
        if n:
            print(f"  {name:<10} {n}")
    rows = load_asks(d)
    print(f"  问过 {len(rows)} 条，其中没答 {len([r for r in rows if not r.get('reply')])} 条")


def do_pack(a) -> None:
    out = Path(a.out).expanduser().resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for p in ROOT.parent.iterdir():
        if p.name == "memory":
            continue
        (shutil.copytree(p, out / p.name) if p.is_dir() else shutil.copyfile(p, out / p.name))
    m = out / "memory"
    (m / "users").mkdir(parents=True)
    if (ROOT / "README.md").exists():
        shutil.copyfile(ROOT / "README.md", m / "README.md")
    shutil.copytree(TPL, m / "users" / "_template")
    shutil.copyfile(ROOT / "memory.py", m / "memory.py")
    leak = [p.name for p in (m / "users").iterdir() if p.name != "_template"]
    if leak:
        sys.exit(f"打包中止：里面混进了真实数据 {leak}")
    print(f"[包] 干净版：{out}（0 条使用者数据）")


def main() -> None:
    ap = argparse.ArgumentParser(prog="memory.py", description="判断台账本")
    sp = ap.add_subparsers(dest="cmd", required=True)

    for name in ("recall", "echo", "stat"):
        sp.add_parser(name).add_argument("--user", default="default")

    p = sp.add_parser("remember")
    p.add_argument("--user", default="default")
    p.add_argument("--kind", required=True)
    p.add_argument("--text", required=True)
    p.add_argument("--date", default=None)
    p.add_argument("--correction-of", default=None, dest="correction_of")

    p = sp.add_parser("ask")
    p.add_argument("--user", default="default")
    p.add_argument("--check", default=None)
    p.add_argument("--log", default=None)
    p.add_argument("--type", default=None)
    p.add_argument("--answer", default=None)

    p = sp.add_parser("pack")
    p.add_argument("--out", required=True)

    a = ap.parse_args()
    {"recall": do_recall, "echo": do_echo, "remember": do_remember,
     "ask": do_ask, "stat": do_stat, "pack": do_pack}[a.cmd](a)


if __name__ == "__main__":
    main()
