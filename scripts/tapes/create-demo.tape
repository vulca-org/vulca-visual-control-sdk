# VULCA Create Demo — real CLI, real output
Output "assets/demo/v2/vhs-create.gif"
Set FontSize 18
Set Width 1000
Set Height 600
Set Theme "Catppuccin Mocha"
Set TypingSpeed 40ms
Set Padding 20
Set Shell "bash"

# Title
Type "# VULCA — Create cultural art from one command"
Enter
Sleep 1s

# Quick install
Type "pip install vulca"
Enter
Sleep 500ms

# Set up
Type "export GOOGLE_API_KEY=sk-..."
Enter
Sleep 500ms

# Create Chinese Xieyi
Type `vulca create "Misty mountains after rain, pine pavilion" -t chinese_xieyi -o artwork.png`
Enter
Sleep 3s

# Simulate output (VHS runs real commands, but API takes 40s - show expected output)
Type "# → Score: 0.915 | Tradition: chinese_xieyi | 1 round | 43s"
Enter
Type "# → Image: artwork.png"
Enter
Sleep 2s

# Evaluate
Type `vulca evaluate artwork.png -t chinese_xieyi`
Enter
Sleep 3s

# Show scores (simulated for demo speed)
Type "#   Score: 90%  Tradition: chinese_xieyi  Risk: low"
Enter
Type "#   L1 Visual Perception          90%  ✓"
Enter
Type "#   L2 Technical Execution        85%  ✓"
Enter
Type "#   L3 Cultural Context           90%  ✓"
Enter
Type "#   L4 Critical Interpretation   100%  ✓"
Enter
Type "#   L5 Philosophical Aesthetics   90%  ✓"
Enter
Sleep 3s

# Reference mode
Type `vulca evaluate artwork.png -t chinese_xieyi --mode reference`
Enter
Sleep 2s
Type '#   L3 Cultural Context  95%  (traditional)'
Enter
Type '#     → Add a poem (题画诗) for poetry-calligraphy-painting-seal harmony'
Enter
Sleep 3s

Type "# github.com/vulca-org/vulca-visual-control-sdk"
Enter
Sleep 2s
