# XHS 文案 · 简体中文 · 7-slide carousel(中文化版)

## 标题候选(20 字内,选其一)

- 同 prompt 同 model,Vulca 让 AI 生图控制力上一个台阶
- 给 OpenAI gpt-image-2 装一个工具链(开源)
- 我们做了一个让 AI 生图可控的开源工具

## 正文(直接复制,~880 字,XHS 限 1000)

```
同样的 prompt,同样的 OpenAI gpt-image-2 模型——加上 Vulca 工具链,出图差距像两个产品。

slide 1 是核心对照实验:左边是裸 API 调用(直接给"工笔风格"指令,模型把 Glasgow 街景刷成统一水彩滤镜),右边是 Vulca 工具链处理(同 prompt 同 model,但通过 design.md 锁住"加层式"风格 + tradition_tokens + color_constraints,输出加进画意元素而保留照片原本的红砖、紫外套女孩、Glasgow 大教堂尖塔)。

区别只在三个 markdown 文件。Vulca 提升的不是模型本身,是"调用模型的可控性"。

slide 2 完整效果。北宋《千里江山图》(王希孟,1113)的色谱和工笔重彩技法被转译成 prompt token,加进 OpenAI gpt-image-2 的调用。gpt-image-2 输出加层式跨文化生图,additive overlay 不是 unified wash 滤镜。

slide 3 拆图能力(layers_split)。Vulca 集成 YOLO + Grounding DINO + SAM + SegFormer,把任意一张生成图拆成 9 个有名的语义层 + 1 个 residual = 10 层。每层 RGBA 独立可编辑。灯笼那层"碎",是 SAM 在多实例输入(一行 6 个分散灯笼)上的真实分割形态——单 bbox 单 mask 限制,如实展示而不修饰。

slide 4 重绘能力(layers_redraw)。挑灯笼这一层,prompt 改"朱砂 +15%, 三矾九染 depth richer",gpt-image-2 直接输出工笔重彩重绘版。同一层、两种处理:alpha 隔离保留 vs LLM 重绘再创作,agent 按意图选。

slide 5 评分能力(evaluate_artwork)。L1=0.78 / L2=0.65 / L3=0.72 / L4=0.75 / L5=0.65 加权 0.702。L2 不及格,因为三矾九染是多遍 alum 涂层物理叠染——单次扩散模型物理上做不到,这是单次模型类技术的天花板,不是 Vulca 瓶颈。strict-rubric 给 reject,maintainer 给 user-override-accept,两条记录都进 plan.md。这是双判决 provenance:严苛规则保留诚实,人保留否决权。

slide 6 整个项目就是三个 markdown 文件:proposal.md / design.md / plan.md + 一个目录的产物。Pixel 从 markdown 复现。markdown 才是产品。

slide 7 其他能力速览。Vulca 一共集成 22 个 MCP tools——这次 carousel 用了 4 个(layers_split / layers_redraw / evaluate_artwork / generate_image)。还有 inpaint_artwork(局部填补)、search_traditions(13 种文化传统)、layers_edit(透明/移动/锁定)等 18 个,可以组合出更多工作流。

Vulca 是开源的,今天连 ship 了 v0.17.12 / 13 / 14 三连发——评论区第一条放 GitHub + pip install 指令(最新 0.17.14)。

#AI生图 #OpenAI #gpt-image-2 #开源工具 #工笔重彩 #千里江山图 #跨文化设计 #AgentNative #ChineseGongbi #vulca
```

## 置顶评论(发布后自己评论 + 长按设为置顶)

```
GitHub: https://github.com/vulca-org/vulca-visual-control-sdk

pip install "vulca[mcp]==0.17.14"

这次 carousel 是 dogfood 的活样本:跑 iter 0 时遇上 gpt-image-2 GA 拒收 input_fidelity,治了 → v0.17.12;跑 decompose 时发现 DINO-object 路径在低置信度下静默标 detected,加了透明性 gate → v0.17.13;最后把 inpaint_artwork(mask_path) + layers_redraw 重塑 + layers_paste_back 三件套合一发 → v0.17.14。三个 ship 全在同一天。v0.17.14 让"编辑一层 → 贴回源图"这个机制纯 MCP 跑通(不再要 Python 里手搓 cream 平底);slide 4 RIGHT 的视觉等价仍走 generate_image 路径,多实例稀疏 alpha 的 per-lantern 重绘是 v0.18 的工作。
```

## 发布建议

- **发布时间**:工作日晚 19:00–22:00 中国 time,XHS organic 流量峰值
- **emoji**:正文我没加,你贴前可以补 1–2 个(🏮 / 🎨 / ✨)做视觉点缀,XHS 算法对适度 emoji 友好
- **冷启动**:发完 30 min 内自己回复 1–2 条评论(刷互动信号)
- **数据观察**:24h 后看曝光 / 点赞 / 收藏 / 评论比。前 3 张图(slide 1/2/3)的看完率决定整体表现
- **后续**:24h 后如果数据 OK,我再发 dev.to + X(英文那两条等你发完 XHS 喊一声"走 A"我就启动)

## 自审清单(发前再扫一眼)

- [ ] 7 张图都对(slide 1=核心对比、slide 2=hero、slide 3=拆图、slide 4=重绘、slide 5=评分、slide 6=文件树、slide 7=其他能力)
- [ ] 标题字数 ≤ 20 字
- [ ] 正文字数 ≤ 1000 字(当前 ~880 字)
- [ ] 「文章阁」「清风阁」如果你想加进文里要简体(slide 上的中文招牌图保留繁体是图像美学,正文统一简体)
- [ ] L2 = 0.65 不是 0.55(plan.md 真值)
- [ ] hashtag 10 个,XHS 上限
- [ ] 置顶评论的 `pip install "vulca[mcp]==0.17.14"` 双引号别漏(zsh 不加双引号会把 `[mcp]` 当 glob 解释)
