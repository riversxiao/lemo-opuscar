---
name: lemo-dialogue
description: 为 Lemo-Opuscar / Lemo-DeepSeek 片子定稿旁白与对白。在 TREATMENT 之后、TTS 之前调用：输出增强 lines.json（含 speaker/want/function），过句长与钩子门禁，做去 AI 味润色，再交给 core/tts。用于讲解片 VO 与可选角色对白；不是 Seedance/短剧出片，不改引擎与 STYLE 不变式。
---

# Lemo-Dialogue（台词定稿）

把「有味的一句」写成可进 TTS 的 `lines.json`。细则以库根 [`DIALOGUE.md`](../../../DIALOGUE.md) 为准；TTS 旗标见 [`TECHNIQUE.md`](../../../TECHNIQUE.md) §4。

## 何时用

- 写完或改完 `TREATMENT.md`，片子需要旁白 / 对白  
- 用户抱怨台词干、像说明书、AI 味重  
- DeepSeek 生产循环里 **tts 之前** 的强制一步  

无 VO：TREATMENT 声明即可，本 skill 输出空列表并退出。

## 输入

1. 项目目录下的 `TREATMENT.md`（题材、时长、有无 VO、叙述性格）  
2. 目标时长（秒）与语言（默认跟用户写作语言）  
3. 可选：旧 `lines.json` / `audio/lines.json`（修订模式）  
4. 模式：`讲解`（默认）或 `角色戏`

## 输出

项目内一份定稿旁白文件（路径与风格一致，常见 `lines.json` 或 `audio/lines.json`），每条至少：

```json
{
  "id": "l1",
  "speaker": "VO",
  "want": "用反差数字抓住注意力",
  "function": "hook",
  "text": "画面或字幕上的字",
  "say": "朗读文本，与 text 同句可加标点",
  "voice": "zh-CN-YunxiNeural",
  "speed": 1.0
}
```

英文片 `voice` 用 Kokoro 名（如 `af_sarah`）。`function` ∈ `hook|turn|evidence|payoff|sting`。

另用 5 行以内报告：总字数、估时（默认 4.5 字/秒）、门禁是否通过、相对目标 ±15%。

## 步骤（短、可执行）

1. **读** `$LIB/DIALOGUE.md` 与 TREATMENT；确认有无 VO、讲解 vs 角色戏。  
2. **起草** 旁白拍：讲解默认；每句填 `want` + `function`；前 3 拍内必须有 `hook`。  
3. **一句一动作（zenstory）**：删掉不改变信息状态、也不能变成画面动作的句子；禁止金句升华与「今天我们来讲」。  
4. **门禁（novel-script 取向）**  
   - 中文单句 ≤ 35 字  
   - `hook` 在前 3 个旁白拍  
   - 估时 = 总字数 / 4.5，落在目标时长 ±15%（并给画面留白）  
   - `say` 与画面/字幕同句，禁止缩短意译  
5. **活人感（huoren-write 取向）**：不新增事实；拆三连排比 / 假精确 / 万能安抚 / 升华收尾；保 TREATMENT 里的叙述声口。  
6. **角色戏才做三问**（否则跳过）：每人要什么 / 什么行动 / 说哪句；遮名仍可辨声口。  
7. **写盘** `lines.json`；**不要**在此步调用视频大模型；**不要**改 `ease.js` / 引擎核心。  
8. **交接**：告知下一步按 `AGENTS.deepseek.md` 跑 `tts_zh.py`/`tts.py` + `asr_check.py`；未过门禁则拒绝交接。

## 不做

- 不接 Seedance / 可灵 / 即梦 / 分镜出片链  
- 不重写 `STYLE.md` 不变式或 demo 引擎  
- 不代替 `asr_check`；念错与吸引力是两层  

## 与 DeepSeek 技能的关系

日常出片仍走 [`lemo-deepseek`](../lemo-deepseek/SKILL.md)。本技能是台词子步骤：  
`TREATMENT → **lemo-dialogue** → demo/内容层 → tts → …`
