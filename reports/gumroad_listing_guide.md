# Gumroad 上架指南 — AI 漫剧 E01 完整包

> 生成时间：2026-07-19
> 项目：AI 漫剧《我变成僵尸后全校跪求我别死》
> 账号：chfr1982
> 上架者：Eric

---

## 一、可行性检查 ✅

### API 自动上架可行性

| 检查项 | 结果 |
|:------|:----:|
| Gumroad API v2 文档地址 | `https://api.gumroad.com/v2` |
| 创建/编辑产品 API | ❌ **不可用**（GitHub issue #4019，截至2026-07 仍为高优先级待实现） |
| 当前 API 能力范围 | 仅支持：读取产品列表、管理 license key、查询销售/订阅 |
| 现有 SDK/CLI | ❌ 无官方 Python SDK 或 CLI 工具 |
| **结论** | **只能通过 Gumroad 网页界面手动上架** |

> 如需自动上架，请关注 https://github.com/antiwork/gumroad/issues/4019 进度
> 当前使用 curl 或 Python requests 无法创建产品 — API 端点尚未开放

| 检查项 | 状态 | 说明 |
|:------|:----:|:-----|
| Gumroad 账号 | ✅ 可用 | 账号 `chfr1982`，已上架 6 款 3D 模型 |
| 已有 3D 模型在售 | ✅ 6 款 | 验证通过 |
| 支付收款 | ✅ PayPal 中国账户可收 USD |
| 税务 | ⚠️ 建议填写 W-8BEN | 非美国税务身份声明 |
| 产品资产 | ✅ 完整 | 6 张关键帧 + 6 段配音 + 故事脚本 |
| SDK/CLI 一键上架 | ❌ 无 | 需手动通过浏览器上架 |

**结论：** 账号就绪，资产齐全，可以直接上架。

---

## 二、产品配置

### 2.1 基本信息

| 字段 | 内容 |
|:----|:------|
| **产品名 (EN)** | AI Comic Drama: Zombie School E01 — Complete Pack |
| **产品名 (CN)** | AI 漫剧《我变成僵尸后全校跪求我别死》E01 完整包 |
| **定价** | **$4.99 USD** |
| **分类** | Digital Comics / AI Art / Audio |
| **License** | Personal Use Only |
| **联盟佣金** | 20-30%（推荐 20% 起步） |
| **自动交付** | ✅ 购买后即时发送下载链接 |

### 2.2 产品内容

这个包包含：

1. **6 张高分辨率关键帧 (PNG)**
   - E01_S01_key.png ~ E01_S06_key.png
   - 动漫风格 AI 绘制，每帧均可作壁纸/收藏
   - 文件合计 ~843 KB

2. **6 段中文配音 (WAV)**
   - E01_S01_tts.wav ~ E01_S06_tts.wav
   - AI 语音合成，高保真 16-bit WAV
   - 文件合计 ~556 KB

3. **故事脚本 (Markdown/PDF)**
   - 完整 E01 分镜头脚本
   - 包含每帧视觉描述、对白、旁白、情感标注
   - 可用于学习、二次创作、翻译

### 2.3 交付文件结构

购买后买家收到的文件包：

```
zombie-school-E01-complete/
├── images/
│   ├── E01_S01_key.png
│   ├── E01_S02_key.png
│   ├── E01_S03_key.png
│   ├── E01_S04_key.png
│   ├── E01_S05_key.png
│   └── E01_S06_key.png
├── audio/
│   ├── E01_S01_tts.wav
│   ├── E01_S02_tts.wav
│   ├── E01_S03_tts.wav
│   ├── E01_S04_tts.wav
│   ├── E01_S05_tts.wav
│   └── E01_S06_tts.wav
└── story_script.md
```

---

## 三、产品描述文案

### 3.1 中文描述（主）

```markdown
# AI 漫剧《我变成僵尸后全校跪求我别死》E01 完整包

🔥 **首集上線！校園奇幻 × 身份反轉 × 懸念開局**

一個普通的高二女生，在一覺醒來後發現自己變成了殭屍。
她能聞到幾百米外的心跳聲，她的瞳孔變成了豎瞳，她的身體正在發生可怕的變化。

但最恐怖的是——
她居然開始覺得，這種感覺還不錯。

同學們開始避開她、議論她、欺負她。只有小林還願意坐在她對面吃午飯。
直到她被不良少年堵在教室後門，體內的力量即將失控——
一隻溫暖的手按住了她的手腕。

「夠了。都回去上課。」

他是誰？他為什麼知道她會遇到危險？
而且——他的手碰到她時，體內的躁動居然安靜下來了。

### 📦 包含內容

- ✅ **6 張 AI 繪製關鍵幀**（PNG 高畫質，可作壁紙收藏）
- ✅ **6 段中文配音**（WAV 無損音頻）
- ✅ **完整故事腳本**（分鏡描述 + 對話 + 旁白）
- ✅ **個人使用授權**

### 🎨 作品亮點

- 日系青春動畫風格，賽璐珞著色 + 油畫筆觸
- 每一幀大片級構圖，光影氛圍拉滿
- 節奏明快，第一集即反轉不斷
- 兼職逆襲 + 神祕力量 + 校園日常多重看點

### 📜 授權說明

- ✅ 個人收藏、欣賞、學習研究
- ✅ 二次創作素材（同人創作、剪輯素材等）
- ✅ 社交媒體分享（須標註出處）
- ❌ 禁止商業販售
- ❌ 禁止去除浮水印
- ❌ 禁止 NFT 鑄造

立即入手，開啟你的 AI 漫劇收藏之旅！
```

### 3.2 English Description

```markdown
# AI Comic Drama: Zombie School E01 — Complete Pack

🔥 **First Episode Launch! Campus Fantasy × Identity Twist × Suspense Opening**

A ordinary high school girl wakes up to find herself turned into a zombie.
She can hear heartbeats from hundreds of meters away. Her pupils have become vertical slits. 
Her body is undergoing terrifying changes.

But the scariest part is——
She's starting to think this doesn't feel so bad.

Classmates avoid her, whisper about her, bully her. Only Kobayashi still sits with her at lunch.
Until she's cornered by delinquents after school, on the verge of losing control——
A warm hand clasps her wrist from behind.

"That's enough. All of you, get back to class."

Who is he? How does he know she was in danger?
And why—when he touches her—does the chaos inside her grow still?

### 📦 What's Included

- ✅ **6 AI-generated keyframes** (High-res PNG, wallpaper-ready)
- ✅ **6 Chinese voice-over tracks** (WAV lossless audio)
- ✅ **Complete story script** (shot-by-shot descriptions, dialogue, narration)
- ✅ **Personal Use License**

### 🎨 Highlights

- Japanese anime art style, cel-shading + oil brush textures
- Cinematic compositions with rich light & shadow
- Fast-paced storytelling with twists in every episode
- Workplace revenge + mysterious powers + campus life

### 📜 License

- ✅ Personal viewing, collection, study
- ✅ Fan creation (doujinshi, video editing, etc.)
- ✅ Social media sharing (with attribution)
- ❌ Commercial resale
- ❌ Watermark removal
- ❌ NFT minting

Get it now and start your AI comic drama collection!
```

---

## 四、SEO 关键词

### 中文关键词
```
AI漫剧, AI动漫, 动态漫, 漫剧, AI短剧, AIGC漫画, 校园僵尸, 僵尸女孩, 
我变成僵尸后全校跪求我别死, 校园逆袭, 身份反转, 轻小说改编, 
AI绘画, Midjourney漫画, ComfyUI, AI配音, AI动画, 动漫壁纸, 
原创漫画, 国产漫画, 新番推荐, 宝藏动漫
```

### English Keywords
```
AI comic drama, AI manga, webtoon, AI animation, motion comic, zombie school,
girl zombie, Chinese animation, donghua, AI art, AI generated comic,
AI illustration, digital art pack, anime keyframes, anime backgrounds,
campus fantasy, supernatural school, reverse harem, mystery
```

### Gumroad 标签 (max 10)
```
AI Comics, Anime Art, Digital Art, Chinese Animation, Zombie, School Fantasy, 
Voice Over, Story Pack, Manga, Donghua
```

---

## 五、封面上架物料要求

| 物料 | 规格 | 说明 |
|:----|:-----|:-----|
| **封面图** | ≥ 1200×800px, PNG/JPG | E01 最佳关键帧（推荐 E01_S06，悬念感强） |
| **预览 GIF** | 可选，< 5MB | 3 帧快速轮播展示画风 |
| **演示视频** | 推荐嵌入 | 使用 E01_preview.mp4 或 E01_release.mp4 |
| **图文预览** | 提供 1 张 + 1 段音频免费试看 | 降低购买决策门槛 |

---

## 六、Gumroad 手动上架步骤

### 6.1 登录
1. 打开浏览器访问 https://app.gumroad.com/
2. 登录账号 `chfr1982`

### 6.2 创建产品
3. 点击右上角 **「Products」** → **「New Product」**
4. 选择 **「Digital」**

### 6.3 填写信息
5. **Name:** `AI 漫剧《我变成僵尸后全校跪求我别死》E01 完整包`
6. **Description:** 粘贴上方 中文描述（主）内容（推荐使用 Markdown 编辑器）
7. **Price:** `$4.99`
8. **Cover Image:** 上传 E01 最佳关键帧作为封面图

### 6.4 上传文件
9. **Content** 区域 → 上传以下文件：
   - ~~`E01_image_set.zip` (843 KB)~~
   - ~~`E01_audio_set.zip` (556 KB)~~
   - **建议：直接上传合并后的 `E01_complete_pack.zip`**（见下文打包说明）

### 6.5 设置
10. **License:** 选 **Personal Use**
11. **Affiliates:** ✅ Enable，佣金设为 **20%**
12. **Auto-responder / 邮件设置:**
    - 购买时发送："感谢购买！下载链接已发到你的邮箱"
    - 购买后 1 天："喜欢这部 AI 漫剧吗？欢迎反馈！"
    - 新集上线时："E02 已发布！限时折扣中"

### 6.6 发布
13. 预览检查
14. 点击 **「Publish」**

---

## 七、打包建议

### 优化方案：合并打包

当前有独立 zip：`E01_image_set.zip` + `E01_audio_set.zip`。

**建议合并为一个完整包上传：**

```bash
cd /Users/eric/Desktop/herness/AI漫剧发布包/packages/
mkdir -p E01_complete
cp E01_image_set.zip E01_complete/
cp E01_audio_set.zip E01_complete/
cp /Users/eric/Desktop/herness/AI漫剧发布包/packages/E01_story_script.md E01_complete/
cd E01_complete && zip -r ../E01_complete_pack.zip . && cd ..
rm -rf E01_complete
```

这样买家解压后收到一个整洁的文件夹结构。

### 未来上架 Bundle 产品

当 E02、E03 也上架后，创建 Bundle：

| 产品 | 定价 |
|:----|:----:|
| 单集 E01 | $4.99 |
| 单集 E02 | $4.99 |
| 第一季全集 (E01-E03) | $14.99 (省 ~$0) |

---

## 八、推广准备清单

| 推广渠道 | 内容 | 状态 |
|:--------|:----|:----:|
| **小红书** | 6 张关键帧 + 种草文案 | ✅ 已准备（见 publish_materials.md） |
| **B站** | E01 视频 + 专栏简介 | ✅ 已准备 |
| **抖音** | 5 条 15 秒切片 | ✅ 已准备 |
| **Twitter/X** | #AIComics #ZombieSchool 配图 | 📝 需生成英文版 |
| **Reddit** r/anime / r/webtoon | 英文版帖子 | 📝 需翻译 |
| **Gumroad Discover** | 平台内推荐 | ✅ 默认开启 |

---

## 九、定价策略参考

| 策略 | 建议 | 原因 |
|:---|:----|:-----|
| **单集定价** | **$4.99** | 低于 $10 冲动消费线 |
| **Bundle 全集** | **$14.99**（3集） | 比单买省 ~$0 |
| **限时折扣** | 上架首周 20% OFF → $3.99 | 拉新冲销量 |
| **免费 Preview** | 提供 S05+S06 图文+配音免费试看 | 降低决策门槛 |

---

## 十、踩坑提醒

| 踩坑点 | 解决方案 |
|:------|:--------|
| ❌ 当月入 >$160 还使用 Free 计划 | 升级 Pro ($10/月，费率降至 3.5%+$0.30) |
| ❌ 中国创作者未填税务信息 | 提交 W-8BEN 声明非美国税务身份 |
| ❌ 封面图不够吸引 | 使用 E01_S06（悬念最强）或 E01_S05（力量爆发感） |
| ❌ 定价超过 $10 | 单集不超过 $9.99，Bundle 可到 $14.99-$19.99 |
| ❌ 没有预览内容 | 至少提供 1 张关键帧 + 1 段音频免费试看 |
| ❌ 没有联盟营销 | 务必开启 Affiliates（20-30%），靠 KOL 帮你推 |

---

> 生成工具：Hermes Agent · gumroad-ops + money-engine 技能
> 文件位置：`/Users/eric/Desktop/herness/AIComics/10_System/reports/gumroad_listing_guide.md`
