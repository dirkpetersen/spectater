# OSU SpecTater Deployment Checklist

## Files Created for You

### Documentation Files (Markdown)
- ✅ **HOW_TO_WRITE_REQUIREMENTS.md** (14 KB)
  - User guide for writing effective requirements documents
  - Can be used as standalone reference
  - Markdown format (viewable in any text editor, web browser, or GitHub)

- ✅ **osu-requirements-template.md** (18 KB)
  - Pre-filled OSU insurance requirements template
  - Contains all your specific requirements:
    - Certificate holder information
    - Insurance company details & ratings
    - General Liability (per occurrence, aggregate, rented premises)
    - Umbrella insurance
    - Liquor liability (conditional)
    - Auto liability (conditional)
    - Workers' compensation
    - Additional insured status
    - Waiver of subrogation
  - Includes PASS/FAIL examples for each requirement
  - Has `[TO BE FILLED: ...]` placeholders for OSU-specific values

### Web Pages (HTML)
- ✅ **templates/guide.html** (21 KB)
  - Beautiful, interactive web page with complete guide
  - Integrated directly into SpecTater application
  - Accessible via button on main page
  - Features:
    - Table of contents for navigation
    - Dark mode support
    - Back button to main evaluator
    - Code examples with syntax highlighting
    - Color-coded good/bad examples
    - Responsive design (mobile/tablet/desktop)

### Application Updates
- ✅ **app.py** (MODIFIED)
  - Added `/guide` route
  - Includes subnet access restriction check
  - Production-ready

- ✅ **templates/index.html** (MODIFIED)
  - Added "Don't know where to start? Look here!" button
  - Links to `/guide` page
  - Matches existing UI styling

## Deployment Steps

### Step 1: Review & Customize (TODAY)
- [ ] Read `osu-requirements-template.md`
- [ ] Fill in all `[TO BE FILLED: ...]` placeholders
- [ ] Verify insurance requirements match OSU policy
- [ ] Review example PASS/FAIL criteria
- [ ] Test the guide page locally

### Step 2: Local Testing
```bash
# Start the application
python3 app.py

# Visit in browser
# Main page: http://localhost:5000
# Guide page: http://localhost:5000/guide
```

### Step 3: Verify Guide Page Works
- [ ] Click "Don't know where to start? Look here!" button
- [ ] Verify guide page loads
- [ ] Test table of contents navigation
- [ ] Test dark mode toggle (🌙 button)
- [ ] Click "Back to Evaluator" button
- [ ] Verify return to main page

### Step 4: Test with Sample Documents
- [ ] Upload sample policy document
- [ ] Upload sample certificate
- [ ] Verify evaluation works
- [ ] Check if results match your expectations

### Step 5: Production Deployment
- [ ] Copy updated `app.py` to production
- [ ] Copy `templates/guide.html` to production
- [ ] Copy `osu-requirements-template.md` to production
- [ ] Copy `HOW_TO_WRITE_REQUIREMENTS.md` to production (optional, for reference)

### Step 6: Configure Static Requirements (Optional)
If you want users to ONLY see your OSU requirements without uploading policy:

```bash
# In .env or .env.default
REQUIREMENTS='osu-requirements-template.md'
```

Then restart the app. Users will only see the submission upload field.

### Step 7: Go Live
- [ ] Verify all updates in production
- [ ] Test from different user locations
- [ ] Monitor for errors in logs
- [ ] Announce feature to users

## What Users Will See

### Before (Main Page)
```
[Title]
[Policy Upload Box]
[Submission Upload Box]
[Go Button]
```

### After (Main Page)
```
[Title]
[Policy Upload Box]
[Submission Upload Box]
[Go Button] [Don't know where to start? Look here!]
                        ↓
```

### New Guide Page
When users click the button, they see:
- Key Principles section
- Document Structure best practices
- Practical Examples with code snippets
- Insurance Requirements Checklist
- Tips for Success
- Template Usage Instructions
- Back button to return

## Customization Reference

### Values to Fill in `osu-requirements-template.md`

Search for `[TO BE FILLED:` in the file to find:

1. **Dates & Policy Details**
   - Policy effective date
   - Applicable organizations/departments

2. **Insurance Amounts** (appears 10+ times)
   - General Liability per occurrence (suggest: $2,000,000)
   - General Aggregate (suggest: $2,000,000)
   - Damage to Rented Premises (suggest: $300,000)
   - Umbrella/Excess Liability (suggest: $1,000,000)
   - Liquor Liability (suggest: $1,000,000)
   - Auto Liability (suggest: $1,000,000)

3. **Entity Information**
   - Legal entity name (Oregon State University)
   - State requirements
   - OSU-specific locations or departments

4. **Contact Information**
   - Department name
   - Contact person/email
   - Exemption process (if any)

## Files You Have

| File | Size | Purpose | Status |
|------|------|---------|--------|
| HOW_TO_WRITE_REQUIREMENTS.md | 14 KB | Standalone user guide | ✅ Ready |
| osu-requirements-template.md | 18 KB | Customizable requirements | ⚠️ Needs customization |
| templates/guide.html | 21 KB | Web guide page | ✅ Ready |
| app.py | Updated | Flask app with /guide route | ✅ Ready |
| templates/index.html | Updated | Main page with guide button | ✅ Ready |
| GUIDE_IMPLEMENTATION_SUMMARY.md | 6.4 KB | Technical details | ℹ️ Reference |

## Quick Links

- **Main evaluator**: http://your-server:5000/
- **Guide page**: http://your-server:5000/guide
- **Template to customize**: `osu-requirements-template.md`
- **User documentation**: `HOW_TO_WRITE_REQUIREMENTS.md`

## Support

### For Users
Direct them to:
1. Click "Don't know where to start? Look here!" button on main page
2. Read through the guide sections
3. Download/reference the template provided

### For Administrators
Reference documents:
- `GUIDE_IMPLEMENTATION_SUMMARY.md` - Technical implementation details
- `HOW_TO_WRITE_REQUIREMENTS.md` - Full user guide content
- `osu-requirements-template.md` - Example requirements structure

## Rollback Plan

If you need to revert changes:

1. Restore original `app.py` from git
   ```bash
   git checkout app.py
   ```

2. Restore original `templates/index.html` from git
   ```bash
   git checkout templates/index.html
   ```

3. Delete `templates/guide.html` (new file)
   ```bash
   rm templates/guide.html
   ```

4. Restart the application
   ```bash
   # The guide page will no longer be available
   # The button will no longer appear on main page
   ```

## Testing Checklist

- [ ] App starts without errors
- [ ] Main page loads correctly
- [ ] "Don't know where to start?" button is visible
- [ ] Clicking button navigates to `/guide`
- [ ] Guide page displays all content
- [ ] Table of contents links work
- [ ] Dark mode toggle works
- [ ] Back button returns to main page
- [ ] Document upload still works
- [ ] Evaluation still completes successfully
- [ ] Access restrictions still apply (if configured)

## Questions?

Refer to:
1. **GUIDE_IMPLEMENTATION_SUMMARY.md** - How it works
2. **CLAUDE.md** - SpecTater architecture
3. **README.md** - Main documentation
4. Code comments in `app.py` and `templates/guide.html`

---

**Ready to deploy!** 🚀

Start by filling in the customization values in `osu-requirements-template.md`, then test locally.
