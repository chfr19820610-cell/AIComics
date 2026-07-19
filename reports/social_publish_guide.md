# 🚀 AI漫剧《我变成僵尸后全校跪求我别死》— 国内发布操作指南

> 生成时间：2026-07-19 | 目标平台：**小红书** + **B站**
> 全集 E01-E05 ✅ 全部完成（30张关键帧 + 30条配音）

---

## 目录

1. [资产状态总览](#一资产状态总览)
2. [小红书图文笔记发布](#二小红书图文笔记发布)
3. [B站视频发布](#三b站视频发布)
4. [social-auto-upload 登录状态](#四social-auto-upload-登录状态)
5. [social-auto-upload 登录指南](#五social-auto-upload-登录指南)
6. [手动发布操作说明](#六手动发布操作说明)
7. [发布策略与时间线](#七发布策略与时间线)

---

## 一、资产状态总览

### 1.1 E01-E05 资产清单

| 集数 | 图片 | 配音 | ZIP包 | 状态 |
|:----:|:----:|:----:|:-----:|:----:|
| **E01** | 6张 key.png ✅ | 6条 dub.wav/tts.wav ✅ | `E01_image_set.zip` + `E01_audio_set.zip` | ✅ **完整** |
| **E02** | 6张 key.png ✅ | 6条 dub.wav/tts.wav ✅ | `E02_image_set.zip` + `E02_audio_set.zip` | ✅ **完整** |
| **E03** | 6张 key.png ✅ | 6条 dub.wav/tts.wav ✅ | `E03_image_set.zip` + `E03_audio_set.zip` | ✅ **完整** |
| **E04** | 6张 key.png ✅ | 6条 tts.wav ✅ | 无 ZIP 包 | ✅ **完整（未打包）** |
| **E05** | 6张 key.png ✅ | 6条 tts.wav ✅ | 无 ZIP 包 | ✅ **完整（未打包）** |

**总计：30张关键帧 + 30条配音音频**

### 1.2 资产路径

```
图片/音频：/Users/eric/Desktop/herness/AI漫剧发布包/packages/{E01..E05}/
ZIP 包：    /Users/eric/Desktop/herness/AI漫剧发布包/packages/E0{1,2,3}_image_set.zip
            /Users/eric/Desktop/herness/AI漫剧发布包/packages/E0{1,2,3}_audio_set.zip
```

> ⚠️ E04/E05 无 ZIP 包，如需打包可执行：
> ```bash
> cd "/Users/eric/Desktop/herness/AI漫剧发布包/packages"
> zip -j E04_image_set.zip E04/*key.png
> zip -j E04_audio_set.zip E04/*.wav
> zip -j E05_image_set.zip E05/*key.png
> zip -j E05_audio_set.zip E05/*.wav
> ```

---

## 二、小红书图文笔记发布

### 2.1 已准备好的文案

已生成的草稿文件：
- `/Users/eric/Desktop/herness/AIComics/10_System/reports/publish_draft_xiaohongshu.md`
  - E01-E03 各一篇完整笔记
  - 含标题（≤20字）、正文、标签、配图建议
- `/Users/eric/Desktop/herness/AIComics/10_System/reports/publish_materials.md`
  - §1.2 小红书种草笔记（完整长文≈800字）
  - §1.1 每帧配文（≤30字）

### 2.2 E01 发布内容推荐（首发）

**标题（≤20字）：**
```
🌸AI漫剧｜变成僵尸后全校跪求我别死 EP01
```

**配图方案（6张）：**
| 序号 | 图片文件 | 画面内容 | 配文 |
|:---:|:---------|:---------|:----|
| 首图 | `E01/E01_S01_key.png` | 女主面对刁难 | **封面+标题** |
| ② | `E01/E01_S02_key.png` | 争辩时刻 | "如果我能证明不是我的错呢？" |
| ③ | `E01/E01_S03_key.png` | 总裁撑腰 | "谁批准你们动她的？" |
| ④ | `E01/E01_S04_key.png` | 身份反转 | "她的身份，你还没资格问。" |
| ⑤ | `E01/E01_S05_key.png` | 冲突升级 | 所有人都以为她只是实习生…… |
| ⑥ | `E01/E01_S06_key.png` | 神秘力量 | 她被开除后，全公司沉默了⚡ |

**正文（种草风，约300字）：**
```
AI制作的原创漫剧《我变成僵尸后全校跪求我别死》第1集上线啦！🎬✨

一份不该看到的方案，一个被冤枉的实习生，
当真相被掩盖，死亡只是开始——
她醒来后，全校都慌了。

🧟‍♀️ 看点
• 校园×丧尸×超能力，脑洞大开
• AI绘制动漫风画面，每一帧都是壁纸
• 节奏紧凑反转不断，第一集就高能预警

📺 完整版见主页/B站搜索"我变成僵尸后全校跪求我别死"
```

**标签策略：**
```
#AI漫剧 #动漫推荐 #动态漫 #好剧推荐 #AIGC #原创动画 #校园丧尸 #漫画推荐 #新番推荐
```

### 2.3 后续集数发布

E02 和 E03 的完整文案已存在于 `publish_draft_xiaohongshu.md`，E04/E05 需参考相同模板续写。

### 2.4 小红书发布方式（二选一）

| 方式 | 说明 | 适用场景 |
|:----|:----|:--------|
| **手动发布** | 登录 [小红书创作者平台](https://creator.xiaohongshu.com) 上传 | 首次发布 / 需要调整排版 |
| **social-auto-upload** | 命令行自动发布（需先登录） | 批量发布（详见§五） |

---

## 三、B站视频发布

### 3.1 已准备好的文案

已生成的草稿文件：
- `/Users/eric/Desktop/herness/AIComics/10_System/reports/publish_draft_bilibili.md`
  - E01-E03 视频标题、简介、标签
  - 发布后操作指南
- `/Users/eric/Desktop/herness/AIComics/10_System/reports/publish_materials.md`
  - §1.3 B站专栏简介（≈200字）

### 3.2 E01 发布内容推荐（首发）

**标题：**
```
【AI漫剧】我变成僵尸后全校跪求我别死 EP01：这份方案是你这实习生能碰的吗？
```

**分区：** 动画 → 动态漫 / 国创

**简介：**
```
🔥 AI制作的原创漫剧第一集上线！

一份不该看到的机密方案，一个被冤枉的实习生女学生。
当所有证据都指向她，当真相被恶意掩盖，
死亡不是终点——她变成僵尸回来了。

🧟‍♀️ 当全校师生发现那个温柔的女同学已经变成了丧尸，
恐惧、震惊、跪求……一切都太迟了。

✨ 制作信息
制作工具：AIComics 全自动漫剧流水线
画风：动漫风 | 配音：AI语音合成

📌 #AI漫剧 #AI动漫 #动态漫 #漫剧 #AIGC #原创动画 #校园 #丧尸 #异能 #国创

🔔 每周更新，点个关注不迷路！
```

**封面要求：**
- 16:9 比例
- 推荐用 E01 女主变身后的场景（如 E01_S06_key.png 或角色高光画面）
- 叠加大字标题 + "EP01" 标记

**标签：**
```
AI漫剧, AI动漫, 动态漫, 漫剧, AIGC, 原创动画, 校园, 丧尸, 异能, 国创
```

### 3.3 注意事项

| 项目 | 要求 |
|:----|:-----|
| 分区 | 动画 → 动态漫 / 国创 |
| 发布时间 | 工作日 19:00-21:00 / 周末 14:00-16:00 |
| 封面 | 16:9，角色高光+集数标注 |
| 动态 | 发布后发一条动态通知粉丝 |
| BGM | 注意版权，B站对未授权音乐管控严格 |

---

## 四、social-auto-upload 登录状态

### 4.1 当前状态

| 平台 | 工作目录 | 登录状态 | Cookie 文件 |
|:----|:--------|:--------:|:----------:|
| **小红书** | `/Users/eric/Desktop/herness/social-auto-upload/` | ❌ **未登录** | cookies 目录为空 |
| **B站** | `/Users/eric/Desktop/herness/social-auto-upload/` | ❌ **未登录** | cookies 目录为空 |
| 小红书 | `/Users/eric/social-auto-upload/` | ✅ **已登录**（账号: main） | `cookies/xhs.json` |
| B站 | `/Users/eric/social-auto-upload/` | ❌ **未登录** | 无 cookie 文件 |

### 4.2 结论

**Desktop workspace 版本 (`/Users/eric/Desktop/herness/social-auto-upload/`)：**
- 小红书：❌ 需要首次登录
- B站：❌ 需要首次登录

**主版本 (`/Users/eric/social-auto-upload/`)：**
- 小红书：✅ 已登录（可复用 cookies）
- B站：❌ 需要首次登录

> 💡 **建议**：将主版本的 `cookies/xhs.json` 复制到 Desktop workspace 版本即可免去小红书登录步骤。
> ```bash
> cp /Users/eric/social-auto-upload/cookies/xhs.json /Users/eric/Desktop/herness/social-auto-upload/cookies/xiaohongshu_uploader/
> ```

---

## 五、social-auto-upload 登录指南

### 5.1 小红书登录

**前置条件：**
- 已登录 [小红书创作者平台](https://creator.xiaohongshu.com) 的浏览器
- 小红书账号已有发布权限

**自动登录（推荐）：**

```bash
# 进入 workspace 版本目录
cd /Users/eric/Desktop/herness/social-auto-upload

# 激活虚拟环境
source venv/bin/activate

# 登录小红书（会弹出浏览器窗口）
python sau_cli.py xiaohongshu login --account main --headed
```

**操作步骤：**
1. 执行上述命令后，Chromium 浏览器窗口会自动打开
2. 浏览器会导航到小红书登录页面
3. **扫码登录**（推荐）或使用手机号/密码登录
4. 登录成功后，Playwright 窗口会显示"▶ Resume"按钮
5. 点击 **Resume** 按钮（重要！不点的话 cookie 不会保存）
6. 终端会显示 `SUCCESS: 🥳 cookie 有效` 即表示登录成功
7. Cookie 会保存在 `cookies/xiaohongshu_uploader/` 目录

**验证登录：**
```bash
python sau_cli.py xiaohongshu check --account main
# 输出：SUCCESS: 🥳 cookie 有效  → 登录成功
```

**通过复制已有 Cookie（快速方案）：**

如果已在 `/Users/eric/social-auto-upload/` 登录过小红书：

```bash
# 复制 cookie 文件到 workspace 版本
cp /Users/eric/social-auto-upload/cookies/xhs.json \
   /Users/eric/Desktop/herness/social-auto-upload/cookies/xiaohongshu_uploader/main.json

# 验证
cd /Users/eric/Desktop/herness/social-auto-upload && source venv/bin/activate
python sau_cli.py xiaohongshu check --account main
```

**使用 upload-note 发布图文笔记：**

```bash
cd /Users/eric/Desktop/herness/social-auto-upload && source venv/bin/activate

# 发布 E01 小红书图文笔记
python sau_cli.py xiaohongshu upload-note \
  --account main \
  --images \
    "/Users/eric/Desktop/herness/AI漫剧发布包/packages/E01/E01_S01_key.png" \
    "/Users/eric/Desktop/herness/AI漫剧发布包/packages/E01/E01_S02_key.png" \
    "/Users/eric/Desktop/herness/AI漫剧发布包/packages/E01/E01_S03_key.png" \
    "/Users/eric/Desktop/herness/AI漫剧发布包/packages/E01/E01_S04_key.png" \
    "/Users/eric/Desktop/herness/AI漫剧发布包/packages/E01/E01_S05_key.png" \
    "/Users/eric/Desktop/herness/AI漫剧发布包/packages/E01/E01_S06_key.png" \
  --title "🌸AI漫剧｜变成僵尸后全校跪求我别死 EP01" \
  --note "AI制作的原创漫剧《我变成僵尸后全校跪求我别死》第1集上线啦！🎬✨\n\n一份不该看到的方案，一个被冤枉的实习生，当真相被掩盖，死亡只是开始——她醒来后，全校都慌了。\n\n🧟‍♀️ 看点\n• 校园×丧尸×超能力，脑洞大开\n• AI绘制动漫风画面，每一帧都是壁纸\n• 节奏紧凑反转不断，第一集就高能预警\n\n📺 完整版见主页/B站搜索"我变成僵尸后全校跪求我别死"\n\n#AI漫剧 #动漫推荐 #动态漫 #好剧推荐 #AIGC #原创动画 #校园丧尸 #漫画推荐 #新番推荐" \
  --tags "AI漫剧,动漫推荐,动态漫,好剧推荐,AIGC,原创动画,校园丧尸,漫画推荐,新番推荐"
```

### 5.2 B站登录

**前置条件：**
- B站账号（已通过实名认证）
- biliup 二进制已安装（✅ 已安装：`~/.social-auto-upload/tools/biliup/macos-aarch64/biliup`）

**登录方式一：使用 sau CLI（推荐）**

```bash
cd /Users/eric/Desktop/herness/social-auto-upload && source venv/bin/activate

# 登录 B站
python sau_cli.py bilibili login --account main
```

操作步骤：
1. 终端会输出一个 URL，类似 `https://passport.bilibili.com/login...`
2. **在默认浏览器中打开这个 URL**
3. 使用 B站账号扫码或账号密码登录
4. 登录成功后，终端会提示验证成功
5. Cookie 保存在 `~/.social-auto-upload/tools/biliup/macos-aarch64/biliupR-v1.2.1-aarch64-macos/` 目录

**登录方式二：使用 biliup 直接登录**

```bash
# 直接使用 biliup 登录
~/.social-auto-upload/tools/biliup/macos-aarch64/biliupR-v1.2.1-aarch64-macos/biliup login
```

**验证登录：**
```bash
cd /Users/eric/Desktop/herness/social-auto-upload && source venv/bin/activate
python sau_cli.py bilibili check --account main
```

**使用 upload-video 发布视频：**

```bash
# B站上传视频
cd /Users/eric/Desktop/herness/social-auto-upload && source venv/bin/activate

python sau_cli.py bilibili upload-video \
  --account main \
  --file "/path/to/E01_video.mp4" \
  --title "【AI漫剧】我变成僵尸后全校跪求我别死 EP01：这份方案是你这实习生能碰的吗？" \
  --desc "🔥 AI制作的原创漫剧第一集上线！

一份不该看到的机密方案，一个被冤枉的实习生女学生。
当所有证据都指向她，当真相被恶意掩盖，
死亡不是终点——她变成僵尸回来了。

🧟‍♀️ 当全校师生发现那个温柔的女同学已经变成了丧尸，
恐惧、震惊、跪求……一切都太迟了。

✨ 制作信息
制作工具：AIComics 全自动漫剧流水线
画风：动漫风 | 配音：AI语音合成

#AI漫剧 #AI动漫 #动态漫 #漫剧 #AIGC #原创动画 #校园 #丧尸 #异能 #国创" \
  --tid 24 \
  --tags "AI漫剧,AI动漫,动态漫,漫剧,AIGC,原创动画,校园,丧尸,异能,国创"
```

> **⚠️ B站 tid 说明：** `--tid` 是分区 ID
> - 24 = 动画 → 动态漫/国创（推荐）
> - 完整 tid 列表可通过 `biliup show` 查看
> - 如果 `24` 不对，请先运行 `biliup show` 查看最新的分区 ID

---

## 六、手动发布操作说明

### 6.1 手动发布小红书图文

1. 打开 [小红书创作者平台](https://creator.xiaohongshu.com)
2. 点击「发布笔记」→「图文」
3. 上传图片：选择 E01_S01~S06 共 6 张 PNG
4. 编辑顺序：首图放 S01（带标题文字的封面）
5. 填写标题：`🌸AI漫剧｜变成僵尸后全校跪求我别死 EP01`
6. 填写正文：使用 §2.2 中的种草文案（约300字）
7. 添加标签：`#AI漫剧 #动漫推荐 #动态漫 #好剧推荐 #AIGC #原创动画`
8. 位置定位：可选（如不定位可留空）
9. 预览确认后发布

### 6.2 手动发布B站视频

1. 打开 [B站创作者中心](https://member.bilibili.com)
2. 点击「投稿」→「视频投稿」
3. 上传已完成渲染的 MP4 视频文件
4. 填写标题：`【AI漫剧】我变成僵尸后全校跪求我别死 EP01：这份方案是你这实习生能碰的吗？`
5. 填写简介：使用 §3.2 中的简介文案
6. 选择分区：动画 → 动态漫 / 国创
7. 添加标签：`AI漫剧, AI动漫, 动态漫, 漫剧, AIGC, 原创动画`
8. 设置封面：上传 16:9 封面图（角色高光画面+集数标注）
9. 设置发布时间：工作日 19:00-21:00 / 周末 14:00-16:00
10. 提交审核

### 6.3 B站发布后操作

```markdown
📢 发布动态模板：
"AI漫剧《我变成僵尸后全校跪求我别死》EP{集数}已上线！快来追番~ 🔗链接"
配图：对应集数的关键帧
```

---

## 七、发布策略与时间线

### 7.1 推荐发布时间线

| 日期 | 小红书 | B站 | 备注 |
|:----:|:------|:----|:----|
| **Day 1** | 发布 E01 图文笔记（6张图+文案） | 发布 E01 视频 | 首发双平台同步 |
| **Day 2-3** | 发布 E02 图文笔记 | 发布 E02 视频 | 保持更新节奏 |
| **Day 4-5** | 发布 E03 图文笔记 | 发布 E03 视频 | 持续输出 |
| **Day 6-7** | 发布 E04 图文笔记 | 发布 E04 视频 | 稳住更新频率 |
| **Day 8-9** | 发布 E05 图文笔记 | 发布 E05 视频 | 首季完结 |

### 7.2 各平台最佳发布时间

| 平台 | 最佳时间 |
|:----|:---------|
| **小红书** | 12:00 / 20:00-22:00 |
| **B站** | 工作日 19:00-21:00 / 周末 14:00-16:00 |

### 7.3 通用标签池

```
#AI漫剧 #AI动漫 #动态漫 #漫剧 #AIGC #原创动画 #国漫 #短剧 #宝藏动漫
```

---

## 附录：快捷命令参考

### 小红书相关

```bash
# 登录
cd /Users/eric/Desktop/herness/social-auto-upload && source venv/bin/activate
python sau_cli.py xiaohongshu login --account main --headed

# 检查登录
python sau_cli.py xiaohongshu check --account main

# 发布图文笔记
python sau_cli.py xiaohongshu upload-note --account main \
  --images 图片1.png 图片2.png 图片3.png 图片4.png 图片5.png 图片6.png \
  --title "标题（≤20字）" \
  --note "正文内容" \
  --tags "标签1,标签2,标签3"

# 复制 cookie（快速方案）
cp /Users/eric/social-auto-upload/cookies/xhs.json \
   /Users/eric/Desktop/herness/social-auto-upload/cookies/xiaohongshu_uploader/main.json
```

### B站相关

```bash
# 登录
cd /Users/eric/Desktop/herness/social-auto-upload && source venv/bin/activate
python sau_cli.py bilibili login --account main

# 检查登录
python sau_cli.py bilibili check --account main

# 直接使用 biliup 登录
~/.social-auto-upload/tools/biliup/macos-aarch64/biliupR-v1.2.1-aarch64-macos/biliup login

# 上传视频
python sau_cli.py bilibili upload-video \
  --account main \
  --file "视频.mp4" \
  --title "标题" \
  --desc "简介" \
  --tid 24 \
  --tags "标签1,标签2"
```

### 手动发布 URL

| 平台 | 链接 |
|:----|:-----|
| 小红书创作者平台 | https://creator.xiaohongshu.com |
| B站创作者中心 | https://member.bilibili.com |

---

> 📝 **说明：** 小红书发布的是**图文笔记**（6张关键帧+配音图片说明），B站发布的是**漫剧视频**（已完成渲染的MP4文件）。
> 所有文案均已在 reports 目录下准备好，可直接复制使用。
> E01-E03 文案见 `publish_draft_xiaohongshu.md` 和 `publish_draft_bilibili.md`
> E04-E05 可按相同模板续写。
