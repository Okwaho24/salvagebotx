# SalvageBotX

SalvageBotX scans a code folder, repo or zip, breaks it into components, and produces a plan for turning the reusable parts into products: snippet packs, CLI tools and lesson modules.

Pure Python standard library, no dependencies. Git is only needed for the `git` source kind.

## Usage

    python3 salvagebotx.py PATH_OR_URL [--kind local|git|zip|pasted] [--branch BRANCH] [--output-dir DIR]

Examples:

    python3 salvagebotx.py ~/projects/myapp
    python3 salvagebotx.py https://github.com/user/repo --kind git --branch main
    python3 salvagebotx.py ./archive.zip --kind zip --output-dir ./out

## Output

Two files, written to `--output-dir` (or the scanned folder if you don't set one):

- `SALVAGEBOTX_PLAN.md`: a ranked, readable plan
- `salvagebotx_plan.json`: the same plan plus the full component graph

## How it works

1. **Ingest** the source (local folder, git clone, zip, or pasted text).
2. **Decompose** it into files, Python functions and Python classes.
3. **Classify** each component by keywords in its name and path.
4. **Map** components to product forms.
5. **Score** and rank them into a prioritized plan.

## Limits

- Classification and scoring are simple keyword heuristics. Effort and uniqueness scores are fixed placeholders and every item is estimated at 8 hours. Treat the plan as a starting point, not a verdict.
- Deep parsing is Python only. Other languages are listed as files.

## License

MIT. See LICENSE.
