# DeepSeek Flash 多风格对照 · 2026-10-28（北京时间）

模型：`openrouter/deepseek/deepseek-v4.1-flash`  
规程：`$LIB/AGENTS.deepseek.md`「实测调教」五条 + 各片 `BRIEF.md` 引擎锁定  
库：`/workspace/lemo-opuscar-deepseek`  
宿主：OpenCode `run --auto --standalone`（`-s` ASCII session；中文仅在 `--title`）

## 总表

| 风格 | 主题 | 成片路径 | 时长 | 旁白 | 画质观感 | 失败/坑 |
|---|---|---|---|---|---|---|
| Pictogram Motion | 分散投资 | `/workspace/films/fensan-pictogram-ds-v001/fensan-pictogram-ds-v001.mp4` | 31.2 s · 24fps · −14.0 LUFS | 无 VO（标题+鼓点；符合风格「旁白可选」） | 强：章节色、象形、HUD、中文巨号清楚；收束「鸡蛋不要放进同一个篮子」 | 缺字体时需自备 Inter/Noto；官方 music.py 偏长，改用自合成 150BPM 床 |
| Caption News | 流动性 | `/workspace/films/liudong-caption-ds-v001/liudong-caption-ds-v001.mp4` | 30.0 s · 30fps · −14.5 LUFS | 中文 edge-tts 云希 · 有声（2026-10-28 已按画面中文重录，语速 +0%） | 强：黄底关键词 slam、账本图、钩子大数；无实拍仍可读 | 初版旁白是缩短意译、画面是全句→听感「没读全」；必须砍掉 vid/doc 等镜头；demo `mix.py` 绑旧时间轴，另写 `mix_zh.py` |
| Whiteboard | 对冲是什么 | `/workspace/films/duichong-whiteboard-ds-v001/duichong-whiteboard-ds-v001.mp4` | 32.0 s · 24fps · −14.1 LUFS | 中文 edge-tts 云希 · 有声 | 中上：板书 HEDGE/A+B/NET 清楚，笔触真实；信息密度低于官方 111s 样片 | EMSTech 无汉字→板上只能拉丁；禁用 `at(word)`；相机 hold 键需手修；demo music.py 弃用 |

对照片（非本次，仅参照）：Swiss Motion「复利」`fuli-swiss-ds-v001`（同模型、同调教）。

## 跨风格：Flash 哪类最好 / 最难

**最好：Pictogram Motion、Caption News（纯图形版）**  
- 内容层边界清晰（`edl.js` / `SHOTS+timeline+文案`），Flash 很少碰引擎。  
- 中文排版有现成 Noto；节奏靠数据（beats / 0.5s 网格），不易花屏。  
- Pictogram 甚至可无旁白，少一条 TTS 对齐失败链。

**中等：Swiss Motion（上次）**  
- 改 `film.js` 文案+`DUR`/`K` 即可；中文拆句与字幕格式要 BRIEF 写死。

**最难：Whiteboard**  
- `film.js` 几乎整份重写；官方依赖英文 whisper 词级对齐，中文必须改绝对秒。  
- 单线字体无 CJK → 「板中文、嘴中文」做不到，只能「板英文、嘴中文」。  
- 相机路径、笔画窗口、字幕烧录同时要稳，Flash 需多轮 still 修（本次修了 hold / 裁切 / mix 路径）。

## 进一步调教 DeepSeek 的教训

1. **BRIEF 比 STYLE 全文更管用**：写死「允许改的文件名 + 禁止改的文件 + 可用 pose/镜头 k 白名单 + 精确渲染命令」。  
2. **无素材风格要提前声明替代路径**（Caption：只允许 stock/loss/stress/end；否则 Flash 会去 fetch 410MB 实拍）。  
3. **中文 × 词级时间轴**：凡依赖 `words.json` / `at(id,word)` 的风格，BRIEF 必须强制「绝对秒 + 跳过 asr 词对齐」。  
4. **字体与混音是高频翻车点**：Flash 能修（拷系统字体、自写 mix），但 BRIEF 里预置「字体已就位 / mix 可降级」可少烧轮次。  
5. **调教五条仍然成立**：引擎锁定、`K` 压缩、参考 still、中文 `。` 拆句、TTS 回修≤2、`$LIB` 绝对路径、OpenRouter Flash、`-s` 仅 ASCII。  
6. **Flash 擅改编排与数据表，不擅长首次发明笔刷**；难风格继续「官方 demo 底座 + 内容层重写」。  
7. **验收自动化有效**：三片均自检 LUFS≈−14、出 still、写 BUILD_NOTES；可继续加 blackdetect（注意片头故意黑场勿误杀）。

## 路径速查

```
/workspace/films/fensan-pictogram-ds-v001/fensan-pictogram-ds-v001.mp4
/workspace/films/liudong-caption-ds-v001/liudong-caption-ds-v001.mp4
/workspace/films/duichong-whiteboard-ds-v001/duichong-whiteboard-ds-v001.mp4
/workspace/films/COMPARE-multi-style-ds.md
```

各片另有：`TREATMENT.md` · `BUILD_NOTES.md` · `BRIEF.md` · stills。
