# Requirements Guide Web Page - Implementation Summary

## What Was Created

A complete web-based guide for users to learn how to write effective requirements documents. The guide is integrated directly into SpecTater as a new page accessible via a button on the main interface.

### Files Created/Modified

#### 1. **templates/guide.html** (NEW)
- Beautiful, responsive web page with comprehensive guide on writing requirements
- Includes all content from `HOW_TO_WRITE_REQUIREMENTS.md` with enhanced formatting
- Features:
  - Back button to return to main evaluator
  - Dark mode support (matches main app styling)
  - Table of contents for easy navigation
  - Syntax-highlighted code examples
  - Color-coded examples (✅ Good / ❌ Bad)
  - Responsive design for mobile and desktop
  - OSU branding (orange and black colors)

#### 2. **HOW_TO_WRITE_REQUIREMENTS.md** (NEW)
- Markdown reference document
- Can be used standalone or linked from documentation
- Includes all principles, examples, and best practices
- Great for offline reference or printing

#### 3. **osu-requirements-template.md** (NEW)
- Ready-to-customize template with all your insurance requirements
- Pre-filled with your specific requirements:
  - Certificate holder information (name, address)
  - Insurance company details (name, AM Best rating)
  - General Liability coverage (per occurrence, aggregate, rented premises)
  - Umbrella insurance
  - Liquor liability (conditional)
  - Auto liability (conditional)
  - Workers' compensation
  - Additional insured status
  - Waiver of subrogation
- Contains `[TO BE FILLED: ...]` placeholders for OSU-specific values
- Includes concrete PASS/FAIL examples for each requirement

#### 4. **app.py** (MODIFIED)
- Added new Flask route: `@app.route('/guide')`
- Route includes subnet access restriction check (same as main page)
- Renders `guide.html` template

#### 5. **templates/index.html** (MODIFIED)
- Added "Don't know where to start? Look here!" button next to the "Go" button
- Button links to `/guide` page
- Styled to match the secondary action button theme
- Responsive design works on all screen sizes

## User Experience Flow

1. **User lands on main page** (`/`)
   - Sees familiar upload interface
   - Sees new button: "Don't know where to start? Look here!"

2. **User clicks the button**
   - Navigates to `/guide` page
   - See comprehensive guide with:
     - Key principles for writing requirements
     - Document structure best practices
     - Practical examples
     - Insurance requirements checklist
     - Tips for success
     - Template usage instructions

3. **User reads the guide and navigates**
   - Table of contents for quick jumping
   - Dark mode support
   - Back button to return to main evaluator

4. **User goes back to main page**
   - Clicks "Back to Evaluator" button
   - Returns to upload interface ready to create requirements

## Key Features

### Content Structure
- **Key Principles** - What makes a good requirement
- **Document Structure** - How to organize requirements
- **Practical Examples** - Real examples of good vs. bad requirements
- **Insurance Requirements** - Specific checklist for insurance evaluations
- **Tips for Success** - Common pitfalls and best practices
- **Using the Template** - How to get started with the template

### Visual Design
- ✅ Clean, modern interface
- ✅ OSU brand colors (orange and black)
- ✅ Dark mode support with localStorage persistence
- ✅ Responsive design (works on mobile, tablet, desktop)
- ✅ Color-coded examples (green for good, red for bad)
- ✅ Easy navigation with back button and table of contents

### Accessibility
- Semantic HTML structure
- Clear heading hierarchy
- Good color contrast in both light and dark modes
- Mobile-friendly responsive design

## How to Use

### For Users
1. Click "Don't know where to start? Look here!" on the main page
2. Read through the guide sections
3. Download or reference the template
4. Create your requirements document
5. Upload to SpecTater to test

### For Administrators
1. Fill in the `[TO BE FILLED: ...]` placeholders in `osu-requirements-template.md`
2. Optionally: Set `REQUIREMENTS='osu-requirements-template.md'` in `.env` to auto-load
3. Users will see the guide button on the main page

## Files to Fill In

Review `osu-requirements-template.md` and fill in:
- `[TO BE FILLED: amount]` - Dollar amounts for coverage limits
- `[TO BE FILLED: State]` - Your state requirements
- `[TO BE FILLED: exact legal entity name]` - OSU's official legal name
- `[TO BE FILLED: contract start/end dates]` - Date handling instructions
- `[TO BE FILLED: OSU department contact]` - Support contact info
- `[TO BE FILLED: special conditions]` - Any OSU-specific policies

## Testing

To verify everything works:

1. **Run the app**
   ```bash
   python app.py
   ```

2. **Visit main page**
   - Open http://localhost:5000
   - Verify "Go" button and new guide button are visible

3. **Click the guide button**
   - Should navigate to http://localhost:5000/guide
   - Page should load with comprehensive guide content

4. **Test navigation**
   - Try table of contents links
   - Test dark mode toggle
   - Click "Back to Evaluator" button
   - Should return to main page

## Integration Points

### Main Page Button
Located in `templates/index.html` at line 364:
```html
<a href="/guide" class="btn btn-outline-secondary ms-2" id="guideBtn">Don't know where to start? Look here!</a>
```

### Flask Route
Located in `app.py` at line 1018:
```python
@app.route('/guide')
def guide():
    """Display the 'How to Write Requirements' guide"""
    # Check subnet access restriction
    if not check_subnet_access():
        return """...""", 403
    return render_template('guide.html')
```

### Template File
- `templates/guide.html` - Main guide page HTML with full styling and content

## Next Steps

1. **Review the guide content** - Make sure it matches your needs
2. **Customize osu-requirements-template.md** - Fill in all placeholders
3. **Test with sample documents** - Verify the guide helps users understand requirements
4. **Deploy to production** - Copy files to production server
5. **Consider static requirements** - Set `REQUIREMENTS` env var to auto-load template

## Notes

- The guide page respects the same IP subnet restrictions as the main page
- Dark mode preference is saved in browser localStorage
- All styling matches the main evaluator page for consistency
- The guide is completely self-contained (no external dependencies beyond Bootstrap)
- Back button and navigation work on all modern browsers
