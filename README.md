# 小旅判断台

> 调用名：`$xiaolv-ludamo-skill`

**我把一套商业判断方法拆成了 121 个具体情形和 1276 条骨架，做成一个随时能问的判断台。**

很多人看商业博主，金句记了一堆，转头遇到自己的生意，还是不知道从哪问起。
真正该学的不是他给什么结论，是他遇到一件真事时，先问哪个变量。

所以这里收的不是金句，是判断依据和它的适用条件。

---

## 安装

```bash
git clone https://github.com/zhangkunlv-ship-it/xiaolv-ludamo.git
cd xiaolv-ludamo
bash install.sh                 # 默认装到 ~/.dsh/skills/xiaolv-ludamo-skill
# 或指定位置
bash install.sh ~/.claude/skills/xiaolv-ludamo-skill
```

`install.sh` 只拷 skill 本体，不碰使用者数据；装完会把文档里的相对路径改成本机绝对路径。

装完验证：

```bash
python3 <安装目录>/memory/memory.py recall --user default
python3 <安装目录>/tools/casegen.py stat
```

---

## 怎么用

```
$xiaolv-ludamo-skill 我这号做了半年一直不温不火，是不是该换赛道
```

不说调用名也能触发。你说"我这生意卡住了""帮我看看这个项目""这行还能不能干"，
或者问"什么是供应链""我现在算哪个阶段"，它自己分诊。

| 你说的是 | 它做什么 |
|---|---|
| 抽象问题、怎么判断、教我 | 走学习线，问一层答一层 |
| 我自己的事卡住了 | 走判断线：验真假 → 问准那一句 → 拆前提 → 给今天能做的动作 |
| 纯信息、闲聊 | 正常答，不套流程 |

---

## 三段真实对话

**① 你说"我想换平台"**

> 普通顾问：列五个平台的优缺点，做一张对比表。
>
> 这里：「你提了四次平台，一次没提货。你不是在挑平台，你在绕一件事——货不在你手上，换到哪个平台都是替别人卖。今天只做一件：挑你卖得最好那款，问一家厂能不能贴你的名字。一个电话。打完把对方原话告诉我。」

**② 你上月说"这周去谈三家厂"，这次回来不提了**

> 普通顾问：不记得，从头问。
>
> 这里：「上次说去谈三家厂。谈了几家。」——不骂，只把账翻出来。

**③ 你半分钟内说了两句相反的话**

> 普通顾问：按最后一句给建议。
>
> 这里：「你半分钟前说这行没前景，现在说想再投二十万。这两句自己听一遍。哪句算数。」

---

## 它凭什么不一样

**一、先验真，再判断。**
你说的每句话先过筛：能验证的 / 糊的 / 只是声称的。第三类直接冻住，不当依据。
不验真就下手，等于在别人的故事上做手术。

**二、问得准，而且不重复问。**
九种问法，按缺哪个事实来选。每一问必须引你自己的原话、只钉一个变量、给你八个字能答完的格式。
一次最多两问，问过的不问第二遍，两轮拿不到数就停。

**三、能引原文，但分得清是谁的原文。**
你的原话（可以加引号、可以回敬你）和库里现成的短句（不加引号、不说成某人说的）严格分开。
一旦混了，所有"你说过……"立刻不值钱。

**四、越用越懂你。**
一人一本账。记得你亲口说的事实、你说过的自我定义句、你上次答应的事、你改过的口。
下次开口第一句就能接上；你一改口，上次那句原话会递回来。只记事实，不记标签。

---

## 结构

```
SKILL.md            主协议：分诊 → 听 → 判 → 问 → 拆 → 给
METHODOLOGY.md      为什么这么设计
tools/
  echo-question.md  九种问法 + 糊词翻译表 + 答完怎么走
  voiceprint.md     账本协议（越用越懂你的实现）
  concepts.md       学习线：十二个词的正解 + 原则 + 流程 + 自查
  quote-bank.md     短句库（加引号规则写在最前面）
  casegen.py        情形库工具：检索 / 扩充 / 校验 / 统计
  case-bank/
    stories.jsonl   121 条具体情形：有人物、有数字、有结果
    seeds.jsonl     61 条抽象母版（要扩充改这里）
    cases.jsonl     1276 条骨架情形（由母版生成）
memory/
  memory.py         账本：recall / echo / remember / ask / stat / pack
  users/_template/  空模板（真实数据不进这里）
README.md           本文件
```

---

## 命令

先 `cd` 到本 skill 的安装目录（SKILL_DIR），再执行：

```bash
M=memory/memory.py

python3 $M recall --user default        # 翻账
python3 $M echo   --user default        # 直接给三句开场素材
python3 $M remember --user default --kind biz   --text "做跨境半年" --date 2026-11-24
python3 $M remember --user default --kind quote --text "我不是能狠下心的人"
python3 $M remember --user default --kind num   --text "月利八千" --correction-of "月利三千"
python3 $M ask --user default --check "货是不是你自己的？"
python3 $M ask --user default --log "这周谈了几家" --type 事实 --answer "零家"
python3 $M stat --user default
python3 $M pack --out /tmp/clean        # 打一个 0 数据的干净包

# 情形库
G=tools/casegen.py
python3 $G stat                                        # 分布
python3 $G search --type 层级错判 --level 中 --industry 电商跨境
python3 $G search --kw 复购                             # 关键词（含同义词）
python3 $G generate --target 1276                       # 加完母版后重新生成
python3 $G validate                                     # 字段/重复校验
python3 $G story --type 层级错判 --level 中 --industry 电商跨境   # 取一条具体故事（优先）
python3 $G story --kw 复购                               # 按关键词找故事
```

`--kind`：`biz` 业务 ／ `num` 数字 ／ `act` 已做动作 ／ `promise` 承诺 ／ `quote` 原话 ／ `voice` 语言指纹 ／ `conflict` 冲突 ／ `correction` 改口

---

## 数据与隐私

- 只写本机 `~/.xiaolv-ludamo/`。不进仓库、不进 git、不上传。
- 只记用户亲口说的事实和原话。不记标签、不记评分、不记"他属于哪一类"。
- 随时可查可删：`stat` 看条数，`rm -rf ~/.xiaolv-ludamo/memory/users/<id>` 删人。
- 要分享只发 `pack` 出来的干净包，里面自检 0 条真实数据。

---

## 边界

- 这是判断方法的实现，不是任何人的本人，也不是任何人的录音整理。
- 适合商业判断、执行卡点、概念纠错。不替代法律、医疗、财务意见。
- 语气硬是设计出来的，但只动行为，不动人。事实不够就先问，不下判断。

---

## 许可

本仓库的文字与代码归本仓库所有。方法层面的通用商业常识属于公共知识，谁都能用；
本仓库的具体表达（问法、话术、情形、账本协议）请勿原样搬运后署别人的名。

要改：欢迎 fork 后自己重写表达，改完就是你的。

本作品采用 CC BY-NC-SA 4.0 许可（署名—非商业性使用—相同方式共享）。
