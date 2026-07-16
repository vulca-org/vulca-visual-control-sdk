# English caption pack - Post #2 Trump

## Version A - Twitter thread hook (<=280 char)

I let Claude decompose Donald Trump's Butler 2024 photo - one 387x258 news frame, 6 independent subjects (Trump + 3 agents + flag + sky) plus a full face anatomy of the mugshot. Vulca ran YOLO+DINO+SAM+SegFormer. Zero manual masking. Thread below.

## Version B - dev.to blog intro (paragraph)

Second test of the agent-native split: the LLM is the brain, the SDK is the hands and eyes, and there is no model call inside the library itself. I handed Claude Code three Trump photos - the Butler 2024 shooting frame, the 2023 Fulton County mugshot, and a 2025 Oval Office portrait - and asked for a full decomposition. The hard one is Butler: overlapping agents, a clinging flag, a cramped 387x258 news crop. Claude read the photo, wrote a JSON plan with `sam_bbox` hints to separate the overlapping figures, and Vulca stitched YOLO + Grounding DINO + SAM + SegFormer into a hierarchical resolve with a residual "honesty" layer. Six subjects came out cleanly. The manifest went back to the agent for a quality check before anything was surfaced. Three photos, one pipeline, 485 layers across the wider 47-image showcase, zero manual masking. Source: https://github.com/vulca-org/vulca-visual-control-sdk

## Version C - Show HN title + TLDR

Title: Show HN: I gave Claude Code an image-decomposition SDK and asked it to post to Xiaohongshu

TLDR para 1: Vulca is a small Python SDK that turns an image plus a JSON plan into a stack of PNG layers - subject, individual objects, a per-face-part breakdown, and a residual layer so nothing is hidden. It stitches YOLO, Grounding DINO, SAM and SegFormer behind a single `decompose()` call. No LLM lives inside the SDK.

TLDR para 2: The thesis is agent-native: Claude Code is the brain (reads pixels, writes plans, validates manifests), Vulca is the hands and eyes (runs the pipeline, returns structured evidence). The Butler 2024 Trump frame is the stress test - one small chaotic news photo, six overlapping subjects, fully automated. Repo + full showcase linked in comments.
