#!/bin/bash
# ─────────────────────────────────────────────────────────────
#  DJ LAB SIAM — Deploy to GitHub Pages
#  วิธีใช้: เปิด Terminal แล้วรัน:
#    bash ~/Claude/Projects/MARKETING\ PLAN/DEPLOY_GITHUB.sh
# ─────────────────────────────────────────────────────────────

set -e  # stop on error
cd "$(dirname "$0")"
echo "📁 Working in: $(pwd)"

# ── Step 1: Remove failed git attempt if exists ──────────────
if [ -d ".git" ]; then
  echo "⚠  Removing old .git folder..."
  rm -rf .git
fi

# ── Step 2: Init + configure ─────────────────────────────────
git init
git branch -m main
git config user.email "djlabsiam@gmail.com"
git config user.name "DJ LAB SIAM"
echo "✓ Git initialized"

# ── Step 3: Stage all files ───────────────────────────────────
git add .
echo "✓ Files staged ($(git status --short | wc -l | tr -d ' ') files)"

# ── Step 4: Commit ────────────────────────────────────────────
git commit -m "Initial commit — DJ LAB SIAM landing page

- index.html (main landing page)
- Meta Pixel placeholder (replace YOUR_PIXEL_ID)
- Fonts: Prompt + Noto Sans Thai
- Pioneer DJ Authorized Dealer + DJ School
- Location: Lido Connect, Siam Square"
echo "✓ Committed"

# ── Step 5: Add GitHub remote ─────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════"
echo "  ⚡  ขั้นตอนต่อไป — ทำบน GitHub.com ก่อน:"
echo ""
echo "  1. ไปที่ https://github.com/new"
echo "  2. Repository name: djlabsiam"
echo "  3. Set to: Public"
echo "  4. ❌ อย่าเช็ค 'Add README'"
echo "  5. Click 'Create repository'"
echo ""
echo "  แล้วกลับมารัน:"
echo "    git remote add origin https://github.com/YOUR_USERNAME/djlabsiam.git"
echo "    git push -u origin main"
echo ""
echo "  จากนั้นเปิด GitHub Pages:"
echo "  6. Repo Settings → Pages"
echo "  7. Source: Deploy from a branch"
echo "  8. Branch: main / root"
echo "  9. Save → รอ ~1 นาที"
echo "  10. URL จะเป็น: https://YOUR_USERNAME.github.io/djlabsiam/"
echo "════════════════════════════════════════════════════════"
echo ""
echo "  ⚠  แทนที่ YOUR_PIXEL_ID ใน index.html ด้วย Meta Pixel ID จริง"
echo "     ก่อน deploy (หรือแก้หลัง push ได้)"
echo "════════════════════════════════════════════════════════"
