# VULCA Full Demo — complete feature showcase
Output "assets/demo/v2/vhs-full.gif"
Set FontSize 17
Set Width 1000
Set Height 600
Set Theme "Catppuccin Mocha"
Set TypingSpeed 35ms
Set Padding 20
Set Shell "bash"

# === Hero ===
Type "# ╔══════════════════════════════════════════════╗"
Enter
Type "# ║  VULCA — AI-native cultural art creation      ║"
Enter
Type "# ║  pip install vulca | 1104 tests | 21 MCP tools ║"
Enter
Type "# ╚══════════════════════════════════════════════╝"
Enter
Sleep 2s

# === Create ===
Type `vulca create "Misty mountains, pine pavilion" -t chinese_xieyi -o art.png`
Enter
Sleep 2s
Type "#   Score: 0.915 | 1 round | 43s | Image: art.png"
Enter
Sleep 1.5s

# === Evaluate Strict ===
Type `vulca evaluate art.png -t chinese_xieyi`
Enter
Sleep 1s
Type "#   Score: 90%  L1=90% L2=85% L3=90% L4=100% L5=90%  Risk: low"
Enter
Sleep 1.5s

# === Evaluate Reference ===
Type `vulca evaluate art.png -t chinese_xieyi --mode reference`
Enter
Sleep 1s
Type '#   L3 95% → Add poem (题画诗) for 诗书画印 harmony'
Enter
Type '#   L2 85% → Explore texture strokes: axe-cut (斧劈皴), rain-drop (雨点皴)'
Enter
Sleep 2s

# === Fusion ===
Type `vulca evaluate art.png -t chinese_xieyi,japanese_traditional --mode fusion`
Enter
Sleep 1s
Type "#   chinese_xieyi: 93% | japanese_traditional: 90%"
Enter
Sleep 1.5s

# === Layers ===
Type `vulca layers split art.png -o ./layers/ --mode extract`
Enter
Sleep 1s
Type "#   6 layers: background | mountains | mist | landscape | pavilion | calligraphy"
Enter
Sleep 500ms
Type `vulca layers redraw ./layers/ --layer pavilion -i "add autumn colors"`
Enter
Sleep 1s
Type `vulca layers composite ./layers/ -o final.png`
Enter
Sleep 1.5s

# === Tools ===
Type `vulca tools run brushstroke_analyze --image art.png -t chinese_xieyi`
Enter
Sleep 1s
Type "#   Energy: 0.87 — aligns with expressive style ✓ (zero API cost)"
Enter
Sleep 1.5s

# === Studio ===
Type `vulca studio "Cyberpunk ink wash" --provider gemini --auto`
Enter
Sleep 1.5s
Type "#   4 concepts → Generate → L1-L5: 93% → Accepted (round 1)"
Enter
Sleep 1.5s

# === Inpaint ===
Type `vulca inpaint art.png --region "sky" --instruction "golden sunset" --select 1`
Enter
Sleep 1s
Type "#   4 variants → selected v1 → blended (pixels outside bbox preserved)"
Enter
Sleep 1.5s

# === Evolution ===
Type `vulca evolution chinese_xieyi`
Enter
Sleep 1s
Type "#   L3 Cultural Context: 25% → 35% (+10%) | Sessions: 71"
Enter
Sleep 2s

# === Outro ===
Type "# github.com/vulca-org/vulca-visual-control-sdk | pip install vulca"
Enter
Sleep 3s
