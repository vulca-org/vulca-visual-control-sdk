# English caption pack - Post #1 Bieber

## Version A - Twitter thread hook (<=280 char)

I let Claude decompose Justin Bieber's Coachella 2026 photos - 9 slides showing the full layer breakdown + face anatomy. Claude reads -> writes JSON plan -> Vulca runs YOLO+DINO+SAM+SegFormer -> agent checks flags. Zero manual masking. Thread below.

## Version B - dev.to blog intro (paragraph)

I've been experimenting with an agent-native split for image editing: the LLM is the brain, the SDK is the hands and eyes, and there is no model call inside the library itself. To stress-test it, I pointed Claude Code at three Bieber Coachella 2026 frames and asked for a full layer decomposition - subject, stage background, and face parts. Claude read each photo, wrote a small JSON plan describing the targets, and handed it to the Vulca SDK, which stitched YOLO + Grounding DINO + SAM + SegFormer into a hierarchical resolve with a residual "honesty" layer. The manifest came back to the agent for a quality check before anything was shown to a human. Three poses, one pipeline, 485 layers across the full 47-image showcase, zero manual masking. Source: https://github.com/vulca-org/vulca-visual-control-sdk

## Version C - Show HN title + TLDR

Title: Show HN: I gave Claude Code an image-decomposition SDK and asked it to post to Xiaohongshu

TLDR para 1: Vulca is a small Python SDK that turns an image plus a JSON plan into a stack of PNG layers - subject, individual objects, a per-face-part breakdown, and a residual layer so nothing is hidden. It stitches YOLO, Grounding DINO, SAM and SegFormer behind a single `decompose()` call. No LLM lives inside the SDK.

TLDR para 2: The thesis is agent-native: Claude Code is the brain (reads pixels, writes plans, validates manifests), Vulca is the hands and eyes (runs the pipeline, returns structured evidence). This post is the evidence - nine slides of a fully automated Coachella 2026 Bieber decomposition where the only human step was saying "go". Repo + full showcase linked in comments.
