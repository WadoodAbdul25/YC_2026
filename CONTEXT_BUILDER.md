# Context Builder - Deep Codebase Analysis with Gemini

## Overview

The Context Builder is a new component in Gryffin that solves the **context-awareness problem** by analyzing existing codebases before generating new architecture and tasks.

## The Problem It Solves

**Before Context Builder:**
- Gryffin would suggest completely wrong tech stacks (e.g., Flask when Django already exists)
- Would try to reinitialize projects that were already set up
- No awareness of existing code, patterns, or architecture
- Generated conflicting architectures

**After Context Builder:**
- ✅ Analyzes all existing code using Gemini 2.0 Flash (2M token context)
- ✅ Detects project type, tech stack, existing apps/modules
- ✅ Identifies gaps and opportunities
- ✅ Provides recommendations for how to extend the codebase
- ✅ Passes insights to planner so new architecture **extends** existing code

## How It Works

### 1. File Collection
```
gryffin start .
  ↓
Scans target directory for all source files
  ↓
Filters out: .git, node_modules, __pycache__, binaries
  ↓
Collects up to 50MB of code (well within Gemini's 2M token limit)
```

### 2. Gemini Analysis
Sends entire codebase to Gemini 2.0 Flash with a comprehensive prompt:
```json
{
  "project_type": "Django Python Backend",
  "existing_apps": ["FlowSync"],
  "tech_stack": {
    "backend": "Django 5.x",
    "database": "SQLite",
    "frameworks": ["Django", "pytest"]
  },
  "existing_functionality": [
    "Email parsing pipeline",
    "OpenAI integration for responses",
    "Task generation"
  ],
  "gaps_and_opportunities": [
    "No frontend UI",
    "Calendar integration not implemented"
  ],
  "recommendations": {
    "how_to_extend": "Add new Django apps",
    "patterns_to_follow": "Use pipeline pattern",
    "integration_points": "FlowSync/pipeline.py"
  }
}
```

### 3. Context-Aware Planning
The planner receives codebase insights and augments the user prompt:
```python
# Original prompt: "build a folder insight tool"

# Augmented prompt sent to OpenAI:
"""
# EXISTING CODEBASE CONTEXT
Project Type: Django Python Backend
Architecture: Email parser with noise filtering...
Existing Apps: FlowSync
Tech Stack: Django, pytest, OpenAI SDK

# USER REQUEST
build a folder insight tool

# YOUR TASK
Generate architecture that EXTENDS the existing Django project.
Use the same tech stack. Do NOT replace existing code.
"""
```

### 4. README Enhancement
Generated README.md now includes:
```markdown
## Existing Codebase Analysis

### Existing Functionality
- Email parsing pipeline in FlowSync/pipeline.py
- OpenAI integration for response generation
- Task generation with pytest tests

### Gaps & Opportunities
- No frontend UI yet
- Calendar integration incomplete

### Integration Recommendations
**How to Extend**: Add new Django apps for features
**Patterns to Follow**: Use pipeline pattern
**Integration Points**: FlowSync/pipeline.py
```

## Usage

### Basic Usage
```bash
cd your-project/
gryffin start .

# Gryffin will automatically:
# 1. Detect existing code
# 2. Analyze with Gemini (if code exists)
# 3. Generate context-aware architecture
# 4. Extend (not replace) your codebase
```

### Output Files
- `codebase_insight.json` - Full Gemini analysis
- `architecture.json` - Context-aware architecture
- `majortasks.json` - Tasks that extend existing code
- `README.md` - Includes codebase analysis section

### CLI Output
Beautiful formatted output using Rich:
```
📂 Scanning codebase...
✓ Collected 42 files (2.3 MB)

🤖 Analyzing codebase with Gemini 2.0 Flash...
✓ Analysis complete

📊 Project Type
┌─────────────────────────────┐
│ Django Python Backend       │
└─────────────────────────────┘

🏗️  Architecture Summary
  Email parser with noise filtering, response drafting...

💻 Tech Stack
┌───────────┬──────────────────┐
│ Component │ Technology       │
├───────────┼──────────────────┤
│ Backend   │ Django 5.x       │
│ Database  │ SQLite           │
└───────────┴──────────────────┘

✓ Insights saved to codebase_insight.json
```

## Technical Details

### Files Modified
1. **pipeline/context_builder.py** (NEW) - Main context analysis logic
2. **pipeline/planner.py** - Accepts and uses codebase insights
3. **pipeline/executor.py** - Includes insights in README
4. **gryffin_cli/cli.py** - Triggers context builder before planning
5. **requirements.txt** - Added google-generativeai
6. **pyproject.toml** - Added dependencies

### Dependencies
- `google-generativeai>=0.8.0` - Gemini API client
- `rich>=13.0.0` - Beautiful CLI output (already installed)

### Environment Variables
```bash
# .env file
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AIzaSy...  # Required for context analysis
```

### Models Used
- **Context Analysis**: Gemini 2.0 Flash Experimental
  - 2M token context window
  - Fast and cost-effective
  - Temperature: 0.1 (consistent analysis)

- **Architecture/Tasks**: OpenAI GPT-4o-mini
  - Receives augmented prompts with context
  - Generates compatible extensions

## Performance

### Limits
- Max file size: 5MB per file
- Max total size: 50MB (well within 2M token limit)
- Skips: binaries, .git, node_modules, __pycache__

### Typical Analysis Time
- Small project (10 files): ~3-5 seconds
- Medium project (50 files): ~8-12 seconds
- Large project (200 files): ~20-30 seconds

## Benefits

### For Solo Developers
- "I can ask Gryffin to add features to my existing project!"
- No more manually explaining project structure
- Gryffin understands what's already built

### For Teams
- Onboarding new AI assistance: just point at the repo
- Consistent understanding across all team members
- Documentation auto-generated from code

### For Hackathons
- Start with a template/boilerplate
- Gryffin extends it intelligently
- Build iteratively, not from scratch each time

## Example Workflow

```bash
# Day 1: Start fresh
cd my-project/
gryffin start .
# Prompt: "email parser with Django"
# → Creates FlowSync Django app

# Day 2: Add features
gryffin start .
# Gryffin: "Detected Django backend with FlowSync..."
# Prompt: "add a React frontend"
# → Gryffin: "Creating React frontend that integrates with
#            existing Django API at FlowSync/api/"

# Day 3: More features
gryffin start .
# Prompt: "add Google Calendar integration"
# → Gryffin: "Extending FlowSync/task_generation.py to sync
#            with Google Calendar API"
```

## Future Enhancements

- [ ] Cache insights to avoid re-analyzing unchanged code
- [ ] Incremental analysis (only analyze changed files)
- [ ] Support for multiple languages in one project
- [ ] Visualization of architecture from insights
- [ ] Export insights to design docs

## Troubleshooting

### "GEMINI_API_KEY not found"
Add to `.env` file:
```bash
GEMINI_API_KEY=your_key_here
```

### "No existing code detected"
This is normal for new projects. Context Builder only runs when source files exist.

### Files getting skipped
Check:
- File size < 5MB
- Total collected size < 50MB
- File is not binary
- Not in ignored directories (.git, node_modules, etc.)

---

**Built with Gemini 2.0 Flash 🚀**
