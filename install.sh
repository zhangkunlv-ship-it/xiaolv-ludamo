#!/usr/bin/env bash
# 装到本机的 skill 目录，并把文档里的相对路径改成本机绝对路径。
#
#   bash install.sh                 # 默认装到 ~/.dsh/skills/xiaolv-ludamo-skill
#   bash install.sh /目标/路径        # 自定义
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="${1:-$HOME/.dsh/skills/xiaolv-ludamo-skill}"

echo "从 $SRC"
echo "装到 $DEST"
mkdir -p "$DEST"

# 拷本体，不碰使用者数据
for f in SKILL.md METHODOLOGY.md README.md LICENSE install.sh; do
  [ -f "$SRC/$f" ] && cp "$SRC/$f" "$DEST/$f"
done
rm -rf "$DEST/tools" "$DEST/memory"
mkdir -p "$DEST/tools" "$DEST/memory/users"
cp -R "$SRC/tools/." "$DEST/tools/"
cp "$SRC/memory/memory.py" "$DEST/memory/memory.py"
cp -R "$SRC/memory/users/_template" "$DEST/memory/users/_template"
[ -d "$DEST/memory/users" ] || mkdir -p "$DEST/memory/users"
chmod +x "$DEST/memory/memory.py"

# 相对路径 → 绝对路径（只在文档里改，代码不动）
python3 - "$DEST" <<'PY'
import pathlib, sys
dest = sys.argv[1]
subs = [
    ("memory/memory.py", f"{dest}/memory/memory.py"),
    ("tools/casegen.py", f"{dest}/tools/casegen.py"),
]
for p in pathlib.Path(dest).rglob("*.md"):
    s = p.read_text(encoding="utf-8"); o = s
    for a, b in subs:
        s = s.replace(f"M={a}", f"M={b}")
        s = s.replace(f"python3 {a}", f"python3 {b}")
        s = s.replace(f"`{a}`", f"`{b}`")
    if s != o:
        p.write_text(s, encoding="utf-8")
        print(f"  路径已本地化: {p.name}")
PY

echo
echo "装好了。试一下："
echo "  python3 $DEST/memory/memory.py recall --user default"
echo "  python3 $DEST/tools/casegen.py stat"
