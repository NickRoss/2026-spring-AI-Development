# Lecture 3 Rework Plan

## Goal

Continue the Lecture 2 resume-scoring + leaderboard arc. Teach students
context-engineering techniques to improve LLM output quality, and let them
**measure** improvement against a ground-truth set via the existing
leaderboard.

## The Ground-Truth Resume Set

We create a labeled subset of resumes with known "correct" fit scores for the
senior software engineer job req.

### Tiers

- **Gold (`g`-prefixed IDs)** — ~5 resumes
  - Strong, unambiguous fits: right experience, right stack, clear signals
  - Expected score band: 80–100
  - Used as high-end anchors

- **Silver (`s`-prefixed IDs)** — ~5 resumes
  - Clearly weak fits: wrong domain, junior, missing core tech, etc.
  - Expected score band: 0–30
  - Used as low-end anchors

- **Unlabeled (existing numeric IDs)** — the rest
  - No ground truth; noisy "in the wild" cases
  - Used for the actual competition / discussion of edge cases

### ID Convention

- Gold resumes: rewrite `ID` column as `g01`, `g02`, ..., `g05`
- Silver resumes: `s01`, `s02`, ..., `s05`
- Everything else: keep original numeric ID
- Applies in `lecture_3/data/resumes_final.csv` (and matching `final_resumes/`
  directory filenames if we reference files directly)
- Leaderboard `VALID_RESUME_IDS` is loaded from this CSV at startup, so new
  prefixed IDs are accepted automatically after the server restarts

### Sourcing the gold/silver set

**Synthesize** the 10 resumes via Q&A with Nick. Process:

1. Claude asks Nick a series of scoping questions: target persona, relevant
   tech stack, years-of-experience ranges, education norms, industry flavor,
   what "gold-level" signals to include, what "silver-level" signals to
   weaken, length/formatting, etc.
2. Based on answers, generate 5 gold + 5 silver resumes as plain text.
3. **Design constraint**: gold and silver resumes should be *similar* in
   surface form (length, structure, vocabulary, industry). The difference
   should be in substantive signal — depth of experience, seniority of
   responsibilities, scope of projects, specific tech match — not superficial
   cues the model can shortcut on. This makes the discrimination task
   genuinely hard and makes the techniques we teach actually matter.
4. Nick reviews and approves each resume before it lands in the CSV.

## Sorting in the Notebook

Right after `load_resumes`, sort deterministically:

```python
resumes = load_resumes('../data/resumes_final.csv')
resume_list = sorted(resumes.values(), key=lambda r: r['ID'])
```

Then slice by prefix:

```python
gold   = [r for r in resume_list if r['ID'].startswith('g')]
silver = [r for r in resume_list if r['ID'].startswith('s')]
wild   = [r for r in resume_list if r['ID'][0].isdigit()]
```

- Sorting makes sampling reproducible across students regardless of CSV row
  order.
- ASCII ordering puts numeric IDs first, then `g*`, then `s*` — but we
  filter by prefix rather than relying on position, so ordering is just for
  reproducibility of `random.sample`.

## Evaluation

We do **not** assign target numeric scores to gold/silver. Instead we evaluate
**ordinally**: a good scorer must produce

    mean(gold_scores) > mean(silver_scores) > mean(wild_scores)

and, ideally, `min(gold_scores) > max(silver_scores)` (full separation).

Metrics we compute per strategy:

- **Gold–silver gap**: `mean(gold) - mean(silver)` — primary metric, measures
  discrimination. Must be positive; larger is better.
- **Gold–wild gap**: `mean(gold) - mean(wild)` — sanity check.
- **Rank separation**: fraction of `(g, s)` pairs where `score(g) > score(s)`.
  Ranges 0–1; 1.0 = perfect ordering. This is essentially pairwise accuracy /
  a discrete version of AUC.
- **Within-tier spread**: std dev of gold and silver scores. Lower means more
  consistent scoring within a tier.
- **Absolute score band**: do gold scores actually land in a "hireable" range
  (e.g., ≥ 60)? Useful for calibration discussion but not the primary metric.

Primary success criterion for students: **increase rank separation and
gold–silver gap relative to baseline.**

## Leaderboard: Restructure + Per-Lecture Routes

### Move to top-level directory

Currently the leaderboard lives at `lecture_2/leaderboard/`. Move it to a new
top-level `leaderboard/` directory so it's shared infrastructure across
lectures rather than owned by Lecture 2.

    /leaderboard
        app.py
        database.py
        Makefile
        __init__.py
        templates/
            base.html            (optional shared layout)
            lecture2.html        (current leaderboard view, renamed)
            lecture3.html        (new view with metrics column)

### Per-lecture routes

Refactor `app.py` so each lecture has its own namespaced routes and its own
database table (or its own SQLite file). Lecture 2 keeps its current behavior;
Lecture 3 is new and can diverge.

**URL layout:**

- `ai-leaderboard.site/lecture2`              — Lecture 2 HTML view (current behavior)
- `ai-leaderboard.site/lecture2/api/submit`   — submit a score
- `ai-leaderboard.site/lecture2/api/submissions`
- `ai-leaderboard.site/lecture2/api/delete_team`
- `ai-leaderboard.site/lecture2/api/reset`

- `ai-leaderboard.site/lecture3`              — Lecture 3 HTML view (new)
- `ai-leaderboard.site/lecture3/api/submit`
- `ai-leaderboard.site/lecture3/api/submissions`
- `ai-leaderboard.site/lecture3/api/metrics`  — NEW: per-team ordinal metrics
- `ai-leaderboard.site/lecture3/api/delete_team`
- `ai-leaderboard.site/lecture3/api/reset`

Implementation option: one FastAPI `APIRouter` per lecture, mounted under
`/lecture2` and `/lecture3`. Each router has its own `VALID_RESUME_IDS` set
loaded from its own resume CSV, its own DB file
(`leaderboard_lecture2.db`, `leaderboard_lecture3.db`), and its own HTML
template. Shared DB helper functions in `database.py` take a `db_path`
argument (already the case).

### Lecture 3 specific endpoints / behavior

- **`POST /lecture3/api/submit`** — same shape as lecture 2 but also accepts
  an optional `strategy` field (e.g. `"baseline"`, `"decomp"`, `"grounded"`,
  `"rubric"`, `"cot"`, `"custom"`). The submission is keyed by
  `(team_name, strategy, resume_id)` so a team can have multiple strategies
  on the leaderboard simultaneously without team-name suffix hacks.
- **`GET /lecture3/api/metrics?team=...&strategy=...`** — computes, from
  submitted scores:
    - gold–silver gap
    - gold–wild gap
    - rank separation (pairwise g>s fraction)
    - within-tier std dev
  Ground-truth tiers are inferred from resume ID prefixes (`g*` / `s*`).
  Returns JSON; called from the notebook after each strategy run.
- **`GET /lecture3`** — HTML view showing, per team × strategy, the ordinal
  metrics side-by-side. Sortable by gold–silver gap. This is the live
  scoreboard students watch during class.

### Backward compatibility

- Lecture 2 notebook continues to work. Its `submit_score` helper in
  `resume_utils.py` currently targets `http://ai-leaderboard.site/api/submit`
  — update it to `http://ai-leaderboard.site/lecture2/api/submit`. Students
  re-running Lecture 2 code will just need a fresh pull.
- Add a `/` root route that redirects to `/lecture3` (or a lecture picker
  page).
- Old `/api/*` routes can either be kept as aliases to `/lecture2/api/*` for
  one lecture's grace period, or removed cleanly. Recommend: keep as thin
  aliases for one week then delete.

### Deployment notes

- The Dockerfile / Makefile currently lives under `lecture_2/`. Move the
  deployment config to the new top-level `leaderboard/` directory.
- On the server, swap the running container. Both DBs start empty; no
  migration needed (or we copy `lecture_2/leaderboard/*.db` → the new
  `leaderboard_lecture2.db` to preserve existing submissions).

## Techniques Covered in Lecture 3 (in order)

1. **Baseline recap** — monolithic prompt from Lecture 2, run on the 10 labeled
   resumes, establish baseline MAE.
2. **Decomposition** — extract years-of-experience, tech skills, education as
   separate structured calls. Combine with deterministic Python scoring.
3. **Grounding with citations** — require `evidence` field quoting resume text
   for every claim. Reduces fabricated experience / skills.
4. **Rubric + few-shot anchoring** — include explicit weighted criteria and
   2–3 anchor examples in the prompt. Directly attacks the "scores bunch in
   65–75" problem from Lecture 2.
5. **Chain-of-thought via schema ordering** — put a `reasoning` field *before*
   `score` in the Pydantic schema so the model writes reasoning first.
6. **Student choice extension** — pick one:
   - Self-consistency (run N times, median)
   - LLM-as-judge (second model critiques first)
   - Cheap+expensive cascade (Haiku extracts, Sonnet scores)

Each section in the notebook:
- Runs the strategy on all 10 labeled resumes
- Computes metrics vs. ground truth
- Submits to leaderboard under a distinct team suffix
- Appends a row to a results DataFrame
- Ends with a markdown cell prompting reflection

Final cell: plot MAE per strategy as a bar chart.

## Slide Changes

Trim the expense-report walkthrough from ~15 slides to ~5 (just enough to
illustrate each technique once). Repurpose freed space for:

- "How do we even know our LLM is good?" — motivation for ground truth
- Gold/silver tier concept
- MAE / tier accuracy / gold-silver gap as evaluation metrics
- Preview of the 5 strategies students will try
- Closing slide: "Which technique moved your MAE the most? Why?"

## Work Breakdown

1. **Data prep — synthesized resumes**
   - [ ] Q&A session: Claude asks Nick scoping questions (persona, stack,
         YoE ranges, industry, how gold/silver should differ)
   - [ ] Generate 5 gold (`g01`–`g05`) + 5 silver (`s01`–`s05`) resume texts
   - [ ] Nick reviews and approves
   - [ ] Append to `lecture_3/data/resumes_final.csv` (or create a new
         `resumes_lecture3.csv` — TBD)

2. **Leaderboard restructure** (top-level `leaderboard/`)
   - [ ] Create top-level `leaderboard/` directory
   - [ ] Move `lecture_2/leaderboard/` contents there
   - [ ] Split `app.py` into `lecture2` and `lecture3` `APIRouter`s
   - [ ] Separate DB files per lecture; shared `database.py` helpers
   - [ ] Rename current template to `lecture2.html`; create `lecture3.html`
   - [ ] Mount routers at `/lecture2` and `/lecture3`
   - [ ] Move Dockerfile + Makefile to top-level `leaderboard/`
   - [ ] Add `strategy` field to Lecture 3 submission schema
   - [ ] Implement `/lecture3/api/metrics` (ordinal metrics from g/s prefixes)
   - [ ] Update `resume_utils.submit_score` in Lecture 2 to hit `/lecture2/api/submit`
   - [ ] Deploy

3. **Notebook rewrite** (`lecture_3_resume_scorer_improvement.ipynb`)
   - [ ] Setup + sorted load + tier slicing (gold / silver / wild)
   - [ ] Shared eval helper: `evaluate(scores_df)` → gap, rank sep, std dev
   - [ ] Shared submit helper that tags `strategy` per run
   - [ ] Section per technique (baseline → decomp → grounded → rubric →
         CoT-via-schema → choice)
   - [ ] Final comparison DataFrame + bar chart of gold–silver gap per strategy
   - [ ] Fetch `/lecture3/api/metrics` at end to confirm server-side metrics
         match notebook-side

4. **Slide rewrite** (`lecture_3.tex`)
   - [ ] Trim expense example (~5 slides)
   - [ ] Add "How do we know our LLM is good?" motivation
   - [ ] Add gold/silver/wild tier concept
   - [ ] Add ordinal metrics (gap, rank separation)
   - [ ] Update "Your Turn" workflow to match new notebook structure

## Open Questions

- Gold/silver resumes: append to existing `resumes_final.csv`, or new
  `resumes_lecture3.csv` so Lecture 2 data stays untouched?
- Should the Lecture 3 leaderboard show *all* submissions live, or only the
  latest submission per `(team, strategy, resume_id)`?
- Keep `/api/*` legacy aliases for lecture 2 for a grace period, or cut over
  cleanly?
- Should the notebook auto-fetch `/lecture3/api/metrics` or leave that as a
  TODO so students wire it up themselves?
