#!/usr/bin/env python3
"""情形库工具：生成 / 检索 / 校验 / 统计。

用前不需要跑 generate（cases.jsonl 已随仓库提供）。
自己加情形：改 seeds.jsonl，再跑一次 generate。

  python3 casegen.py stat
  python3 casegen.py generate --target 1276
  python3 casegen.py search --type 层级错判 --level 中 --industry 电商跨境
  python3 casegen.py search --kw 复购
  python3 casegen.py validate
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEEDS = HERE / "case-bank" / "seeds.jsonl"
STORIES = HERE / "case-bank" / "stories.jsonl"
EVIDENCE_DIR = HERE / "case-bank" / "evidence"
CASES = HERE / "case-bank" / "cases.jsonl"

# 行业画像：品类 / 渠道 / 货 / 客户
PROFILES = {
    "电商跨境": (["女装", "家居小件", "3C 配件", "饰品"], ["平台店", "短视频", "独立站"], "工厂货", "C 端买家"),
    "实体门店": (["餐饮", "教培", "美业", "社区零售"], ["街边店", "商场店", "社群"], "加盟货", "周边三公里"),
    "制造批发": (["五金件", "建材", "包装材料", "食品原料"], ["展会", "老客户转介", "线上批发"], "自产", "下游厂商"),
    "服务项目": (["设计", "装修", "代运营", "咨询"], ["转介绍", "平台派单", "陌生开发"], "人力", "中小老板"),
    "内容自媒体": (["口播", "图文", "带货", "知识付费"], ["短视频", "公众号", "直播"], "内容", "泛粉与精准粉"),
    "职场个人": (["跳槽", "副业", "转行", "接私活"], ["招聘平台", "人脉", "公开项目"], "技能", "雇主与甲方"),
    "投资合伙": (["店面合伙", "项目跟投", "理财", "借贷"], ["熟人介绍", "社群", "线下局"], "资金", "合伙人与出资方"),
}

# 检索同义词：用户说 A，库里可能写的是 B
SYN = {
    "复购": ["回头", "回购", "再来", "老客户"],
    "流量": ["播放", "曝光", "来的人", "投放"],
    "供应链": ["货源", "贴牌", "供货", "厂"],
    "定价": ["涨价", "价格", "报价", "降价"],
    "团队": ["员工", "招人", "人效", "老员工"],
    "客户": ["买家", "K 端", "甲方", "老客户"],
    "周转": ["现金", "账上", "货款", "压"],
    "转化": ["成交", "没买", "下单"],
    "内容": ["短视频", "文案", "拍摄", "片子"],
    "品牌": ["包装", "视觉", "牌子"],
}

LEVELS = {
    "低": "直接说结论，不解释过程，不铺垫。",
    "中": "先认他对的那一半，再翻另一半。",
    "高": "别教育，只给路径和时间点。",
}


def load_seeds() -> list[dict]:
    if not SEEDS.exists():
        sys.exit(f"缺少 {SEEDS}")
    out = []
    for i, ln in enumerate(SEEDS.read_text(encoding="utf-8").splitlines(), 1):
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError as e:
            sys.exit(f"seeds.jsonl 第 {i} 行不是合法 JSON：{e}")
    return out


def expand(seed: dict, industry: str, level: str, idx: int) -> dict:
    cat, chan, goods, who = PROFILES[industry]
    c = cat[idx % len(cat)]
    sit = seed["situation"].format(C=c, CH=chan[idx % len(chan)], G=goods, K=who)
    return {
        "id": f"K{idx:04d}",
        "type": seed["type"],
        "level": level,
        "industry": industry,
        "situation": sit,
        "misjudge": seed["misjudge"],
        "ask": seed["ask"],
        "flip": seed["flip"],
        "action": seed["action"].format(C=c, CH=chan[idx % len(chan)], G=goods, K=who),
        "tone": LEVELS[level],
        "tags": seed.get("tags", []),
        "seed": seed.get("sid", ""),
    }


def cmd_generate(a) -> None:
    seeds = load_seeds()
    rows, i = [], 0
    # 组合顺序：先保证每个「类型×行业」都有，再补档位，避免前段全是同一类
    combos = [(s, ind, lv) for s in seeds for ind in PROFILES for lv in ("低", "中", "高")]
    combos.sort(key=lambda x: (x[0]["type"], x[1], ["低", "中", "高"].index(x[2])))
    for s, ind, lv in combos:
        if a.target and len(rows) >= a.target:
            break
        rows.append(expand(s, ind, lv, i))
        i += 1
    CASES.parent.mkdir(parents=True, exist_ok=True)
    with CASES.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[生成] {len(rows)} 条 → {CASES}")
    print(f"        来自 {len(seeds)} 条母版 × {len(PROFILES)} 行业 × 3 档")


def load_stories() -> list[dict]:
    if not STORIES.exists():
        sys.exit(f"缺少 {STORIES}")
    return [json.loads(ln) for ln in STORIES.read_text(encoding="utf-8").splitlines() if ln.strip()]


def story_score(r: dict, t: str, lv: str, ind: str, kw: str) -> int:
    s = 0
    if t:
        if r["type"] == t:
            s += 10
        elif t in r["type"] or r["type"] in t:
            s += 4
    if lv:
        s += 6 if r["lv"] == lv else -2
    if ind:
        s += 5 if r["ind"] == ind else 0
    if kw:
        body = " ".join([r["story"], r["verdict"], r["do"], r["out"]])
        if kw in body:
            s += 6
        elif kw in r["who"]:
            s += 2
        elif any(al in body for al in SYN.get(kw, [])):
            s += 3
    return s


def cmd_story(a) -> None:
    """取一条具体故事。默认只给一条。"""
    rows = load_stories()
    ranked = sorted(((story_score(r, a.type, a.level, a.industry, a.kw), r) for r in rows),
                    key=lambda x: -x[0])
    top = [(sc, r) for sc, r in ranked if sc >= 3][: a.limit]
    if not top:
        print(json.dumps({"found": False, "note": "没有匹配。宁可空手，不硬凑。"}, ensure_ascii=False))
        return
    for sc, r in top:
        print(json.dumps({"score": sc, **r}, ensure_ascii=False))


def load_cases() -> list[dict]:
    if not CASES.exists():
        sys.exit(f"缺少 {CASES}，先跑 generate")
    return [json.loads(ln) for ln in CASES.read_text(encoding="utf-8").splitlines() if ln.strip()]


def score(row: dict, t: str, lv: str, ind: str, kw: str) -> int:
    s = 0
    if t:
        if row["type"] == t:
            s += 10
        elif t in row["type"] or row["type"] in t:
            s += 4
    if lv:
        s += 6 if row["level"] == lv else -2
    if ind:
        s += 5 if row["industry"] == ind else 0
    for tag in row.get("tags", []):
        if t and tag in t:
            s += 2
    if kw:
        full = " ".join([row["situation"], row["misjudge"], row["ask"], row["flip"],
                         row["action"], " ".join(row.get("tags", []))])
        core = " ".join([row["misjudge"], row["ask"], row["flip"], row["action"],
                         " ".join(row.get("tags", []))])
        verdict = " ".join([row["misjudge"], row["flip"], " ".join(row.get("tags", []))])
        if kw in core:
            s += 6                      # 正文命中，权重最高
        elif kw in full:
            s += 3                      # 只出现在情形描述里，仍是有效命中
        elif any(alt in verdict for alt in SYN.get(kw, [])):
            s += 3                      # 同义词只认「判定+翻转」两句，动作句太泛不算
    return s


def cmd_search(a) -> None:
    rows = load_cases()
    ranked = sorted(((score(r, a.type, a.level, a.industry, a.kw), r) for r in rows),
                    key=lambda x: -x[0])
    top = [(sc, r) for sc, r in ranked if sc >= 3][: a.limit]
    if not top:
        print(json.dumps({"found": False, "note": "没有匹配。宁可空手，不硬凑。"}, ensure_ascii=False))
        return
    for sc, r in top:
        print(json.dumps({"score": sc, **r}, ensure_ascii=False))


def cmd_validate(a) -> None:
    rows = load_cases()
    need = ["id", "type", "level", "industry", "situation", "misjudge", "ask", "flip", "action", "tone"]
    bad, ids, seen = [], set(), set()
    for r in rows:
        miss = [k for k in need if not r.get(k)]
        if miss:
            bad.append((r.get("id", "?"), f"缺字段 {miss}"))
        if r["id"] in ids:
            bad.append((r["id"], "id 重复"))
        ids.add(r["id"])
        sig = (r["type"], r["level"], r["industry"], r["seed"])
        if sig in seen and a.strict:
            bad.append((r["id"], f"同源重复 {sig}"))
        seen.add(sig)
        for k in ("situation", "misjudge", "flip", "action"):
            if len(r.get(k, "")) < 6:
                bad.append((r["id"], f"{k} 太短"))
    print(f"[校验] {len(rows)} 条，问题 {len(bad)} 处")
    for i, msg in bad[:20]:
        print(f"  {i}: {msg}")
    if not bad:
        print("  全部通过")


def load_evidence() -> list[dict]:
    """真实连麦提炼的判断依据（八字段，不进公开仓库）。"""
    if not EVIDENCE_DIR.exists():
        return []
    out = []
    for f in sorted(EVIDENCE_DIR.glob("*.jsonl")):
        for ln in f.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                r = json.loads(ln)
                r["_file"] = f.stem
                out.append(r)
    return out


def cmd_evidence(a) -> None:
    """按类型/关键词取一条真实判断依据。"""
    rows = load_evidence()
    if not rows:
        print(json.dumps({"found": False, "note": "证据库为空。先跑蒸馏。"}, ensure_ascii=False))
        return
    def sc(r):
        v = 0
        if a.type:
            v += 10 if r.get("type") == a.type else 0
        if a.kw:
            body = " ".join([r.get("case",""), r.get("verdict",""), r.get("line",""), r.get("do",""), " ".join(r.get("tags",[]))])
            if a.kw in body: v += 6
            elif any(al in body for al in SYN.get(a.kw, [])): v += 3
        if a.conflict_only and r.get("conflict"): v += 8
        return v
    ranked = sorted(((sc(r), r) for r in rows), key=lambda x: -x[0])
    top = [(v, r) for v, r in ranked if v >= 3][: a.limit]
    if not top:
        print(json.dumps({"found": False, "note": "没有匹配。"}, ensure_ascii=False)); return
    for v, r in top:
        print(json.dumps({"score": v, **r}, ensure_ascii=False))


def cmd_stat(a) -> None:
    rows = load_cases()
    print(f"[库] {CASES}")
    print(f"  总条数 {len(rows)}")
    by_t: dict = {}
    by_i: dict = {}
    by_l: dict = {}
    for r in rows:
        by_t[r["type"]] = by_t.get(r["type"], 0) + 1
        by_i[r["industry"]] = by_i.get(r["industry"], 0) + 1
        by_l[r["level"]] = by_l.get(r["level"], 0) + 1
    print("  按类型：")
    for k, v in sorted(by_t.items(), key=lambda x: -x[1]):
        print(f"    {k:<12} {v}")
    print("  按行业：", "，".join(f"{k} {v}" for k, v in by_i.items()))
    print("  按档位：", "，".join(f"{k}档 {v}" for k, v in by_l.items()))
    ev = load_evidence()
    if ev:
        from collections import Counter as C
        print(f"  真实证据（evidence/）: {len(ev)} 条，来自 {len({r['_file'] for r in ev})} 个视频")
        print("    类型分布：", "，".join(f"{k} {v}" for k, v in C(r.get('type','?') for r in ev).most_common()))


def main() -> None:
    ap = argparse.ArgumentParser(prog="casegen.py", description="情形库")
    sp = ap.add_subparsers(dest="cmd", required=True)

    p = sp.add_parser("generate")
    p.add_argument("--target", type=int, default=1276)

    p = sp.add_parser("search")
    p.add_argument("--type", default="")
    p.add_argument("--level", default="")
    p.add_argument("--industry", default="")
    p.add_argument("--kw", default="")
    p.add_argument("--limit", type=int, default=1)

    p = sp.add_parser("validate")
    p.add_argument("--strict", action="store_true")

    sp.add_parser("stat")

    p = sp.add_parser("evidence")
    p.add_argument("--type", default="")
    p.add_argument("--kw", default="")
    p.add_argument("--conflict-only", action="store_true", dest="conflict_only")
    p.add_argument("--limit", type=int, default=1)

    p = sp.add_parser("story")
    p.add_argument("--type", default="")
    p.add_argument("--level", default="")
    p.add_argument("--industry", default="")
    p.add_argument("--kw", default="")
    p.add_argument("--limit", type=int, default=1)

    a = ap.parse_args()
    {"generate": cmd_generate, "search": cmd_search, "story": cmd_story,
     "validate": cmd_validate, "stat": cmd_stat,
     "evidence": cmd_evidence}[a.cmd](a)


if __name__ == "__main__":
    main()
