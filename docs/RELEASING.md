# Releasing Wrenify

Guide for maintainers to cut a new release.

## Prerequisites

- Push access to repo
- GitHub CLI installed (`gh`)
- Local build tools working
- Clean working directory

## Semantic Versioning

Wrenify uses [SemVer](https://semver.org/):

- `MAJOR.MINOR.PATCH` (e.g., `0.1.0`)
- **MAJOR**: Incompatible changes (bump when breaking users)
- **MINOR**: New features (backwards compatible)
- **PATCH**: Bug fixes only

Current version: check `pyproject.toml`

## Pre-Release Checklist

Before cutting a release, verify:

- [ ] All tests pass (`poetry run pytest`)
- [ ] Lint clean (`poetry run ruff check .`)
- [ ] Manual test on Linux (full karaoke flow)
- [ ] Manual test on Windows (if changed subprocess/paths)
- [ ] CHANGELOG.md updated
- [ ] README.md screenshots current
- [ ] Version bumped in pyproject.toml
- [ ] All commits pushed to master

## Release Process

### 1. Update Version

Edit `pyproject.toml`:
```toml
[tool.poetry]
name = "wrenify"
version = "0.1.0"  # ← bump this
```

Also update `wrenify/main.py`:
```python
@click.version_option(version="0.1.0", prog_name="Wrenify")
```

Commit:
```bash
git add pyproject.toml wrenify/main.py
git commit -m "chore: bump version to 0.1.0"
git push origin master
```

### 2. Update CHANGELOG

Edit `CHANGELOG.md` and add release notes:
```markdown
## [0.1.0] - 2025-08-19

### Added
- Complete karaoke pipeline
- YouTube song import
- Demucs vocal separation
- WORLD vocoder auto-tune
- Recording with music mixing
- 6 export versions per recording

### Changed
- Removed scoring system (fun over judgment)

### Fixed
- Windows console popups
- Long path issues
```

Commit:
```bash
git add CHANGELOG.md
git commit -m "docs: update changelog for 0.1.0"
git push origin master
```

### 3. Build AppImage Locally

```bash
./build/build_appimage.sh 0.1.0
```

Test it:
```bash
chmod +x dist/Wrenify-0.1.0-x86_64.AppImage
./dist/Wrenify-0.1.0-x86_64.AppImage
```

If it works, continue. If not, fix bugs and retry.

### 4. Tag the Release

```bash
git tag -a v0.1.0 -m "Release v0.1.0"
git push origin v0.1.0
```

### 5. Create GitHub Release

**Option A: Via GitHub CLI (recommended)**
```bash
gh release create v0.1.0 \
    --title "Wrenify v0.1.0 — First Release" \
    --notes-file CHANGELOG.md \
    dist/Wrenify-0.1.0-x86_64.AppImage
```

**Option B: Via GitHub Web**
1. Go to https://github.com/MrRishabThapa/Wrenify/releases
2. Click "Draft a new release"
3. Choose tag `v0.1.0`
4. Title: "Wrenify v0.1.0 — First Release"
5. Description: paste from CHANGELOG
6. Attach: `dist/Wrenify-0.1.0-x86_64.AppImage`
7. Click "Publish release"

### 6. Announce

- Reddit: r/Python, r/linux
- HackerNews: Show HN
- Twitter/X: Screenshots + link
- Personal blog (if you have one)

Post template:
```
🎉 Wrenify v0.1.0 released!

A local-first karaoke studio with:
✅ YouTube song import
✅ AI vocal separation (Demucs)
✅ Auto-tune recording
✅ Runs 100% locally

Linux + Windows support.
100% free and open source (MIT).

Download: [link]
Source: [link]
```

### 7. Monitor Feedback

- Watch GitHub Issues
- Respond to Reddit comments
- Note bugs for v0.1.1 patch

## Hotfix Releases

For urgent bug fixes:

```bash
# Fix the bug
git add .
git commit -m "fix: critical bug"

# Bump patch version
# Edit pyproject.toml: 0.1.0 → 0.1.1
git commit -am "chore: bump version to 0.1.1"

# Tag and release
git tag -a v0.1.1 -m "Release v0.1.1 — Hotfix"
git push origin v0.1.1

# Build and upload
./build/build_appimage.sh 0.1.1
gh release create v0.1.1 \
    --title "v0.1.1 — Hotfix" \
    --notes "Fixes: ..." \
    dist/Wrenify-0.1.1-x86_64.AppImage
```

## Automating with GitHub Actions

See `.github/workflows/release.yml` for automated builds on tag push.