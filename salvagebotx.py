#!/usr/bin/env python3
"""
SALVAGEBOTX™
The No Mercy Code Recycler and Productization Machine
Version 1.0 — Clean & Complete
"""

import asyncio
import ast
import json
import logging
import shutil
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

logger = logging.getLogger("salvagebotx")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

WORKDIR = Path(".salvagebotx_workdir").resolve()
WORKDIR.mkdir(exist_ok=True)

# Models
@dataclass
class IngestResult:
    root_path: Path
    source_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Component:
    id: str
    path: str
    kind: str
    name: str
    language: Optional[str] = None
    purpose: Optional[str] = None
    tech_stack: List[str] = field(default_factory=list)
    inferred_capabilities: List[str] = field(default_factory=list)

@dataclass
class MappedForm:
    id: str
    component_id: str
    form_type: str
    description: str
    audience: str
    notes: str

@dataclass
class ScoredForm:
    id: str
    mapped_form_id: str
    value_score: float
    effort_score: float
    uniqueness_score: float

@dataclass
class ExecutionItem:
    title: str
    description: str
    actions: List[str]
    estimated_effort_hours: float
    projected_value_tier: str

@dataclass
class ExecutionPlan:
    components: List[Component]
    mapped_forms: List[MappedForm]
    scored_forms: List[ScoredForm]
    prioritized_items: List[ExecutionItem]
    graph: Dict[str, Any]

# Ingest
async def ingest(source: str, kind: str, branch: Optional[str] = None, language_hint: str = "txt") -> IngestResult:
    kind = kind.lower()
    if kind == "local":
        p = Path(source).expanduser().resolve()
        if not p.exists() or not p.is_dir():
            raise FileNotFoundError(f"Folder not found: {p}")
        return IngestResult(root_path=p, source_type="local")
    if kind == "git":
        # simple git clone (reuse existing if present)
        safe_name = source.replace("://", "_").replace("/", "_").replace(":", "_")
        target = WORKDIR / f"git_{safe_name}"
        if target.exists():
            return IngestResult(root_path=target, source_type="git")
        import subprocess
        cmd = ["git", "clone"]
        if branch:
            cmd += ["--branch", branch]
        cmd += ["--", source, str(target)]
        subprocess.run(cmd, check=True)
        return IngestResult(root_path=target, source_type="git")
    if kind == "zip":
        zp = Path(source).expanduser().resolve()
        target = WORKDIR / f"zip_{zp.stem}"
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        with zipfile.ZipFile(zp, "r") as zf:
            zf.extractall(target)
        return IngestResult(root_path=target, source_type="zip")
    if kind == "pasted":
        tmp_dir = WORKDIR / "pasted"
        tmp_dir.mkdir(exist_ok=True)
        suffix = ".py" if "python" in language_hint.lower() else ".txt"
        fd, tmp_path = tempfile.mkstemp(suffix=suffix, dir=tmp_dir)
        Path(tmp_path).write_text(source, encoding="utf-8")
        return IngestResult(root_path=tmp_dir, source_type="pasted")
    raise ValueError(f"Unknown kind: {kind}")

# Decompose
CODE_EXTS = {".py": "python", ".js": "javascript", ".ts": "typescript", ".sh": "shell"}
CONFIG_EXTS = {".json", ".yaml", ".yml", ".toml", ".ini"}
DOC_EXTS = {".md", ".rst", ".txt"}

def _new_id() -> str:
    return str(uuid4())

def _infer_kind_and_lang(path: Path) -> Tuple[str, Optional[str]]:
    ext = path.suffix.lower()
    if ext in CODE_EXTS:
        return "code_file", CODE_EXTS[ext]
    if ext in CONFIG_EXTS:
        return "config", None
    if ext in DOC_EXTS:
        return "doc", None
    return "file", None

def _decompose_python_file(path: Path) -> List[Component]:
    components: List[Component] = []
    try:
        src = path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(src)
    except Exception:
        return components
    base = str(path)
    components.append(Component(id=_new_id(), path=base, kind="code_file", name=path.name, language="python"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            components.append(Component(id=_new_id(), path=base, kind="python_function", name=node.name, language="python"))
        elif isinstance(node, ast.ClassDef):
            components.append(Component(id=_new_id(), path=base, kind="python_class", name=node.name, language="python"))
    return components

def decompose(ingest_result: IngestResult) -> List[Component]:
    root = ingest_result.root_path
    components: List[Component] = []
    skip_dirs = {".git", "node_modules", WORKDIR.name}
    for p in root.rglob("*"):
        if not p.is_file() or skip_dirs & set(p.relative_to(root).parts):
            continue
        kind, lang = _infer_kind_and_lang(p)
        if lang == "python":
            components.extend(_decompose_python_file(p))
        else:
            components.append(Component(id=_new_id(), path=str(p), kind=kind, name=p.name, language=lang))
    return components

def classify_components(components: List[Component]) -> List[Component]:
    for c in components:
        tech = []
        caps = []
        purpose = None
        low = c.path.lower() + c.name.lower()
        if c.language == "python": tech.append("python")
        if "bot" in low: caps.append("automation_bot")
        if "cron" in low or "schedule" in low: caps.append("scheduler")
        if "report" in low or "export" in low: caps.append("reporting")
        if "doc" in c.kind: caps.append("documentation")
        if c.kind == "doc" or any(w in low for w in ["tutorial","guide","example"]): caps.append("teachable")
        c.tech_stack = sorted(set(tech))
        c.inferred_capabilities = sorted(set(caps))
        c.purpose = purpose
    return components

def map_to_products(components: List[Component]) -> List[MappedForm]:
    mapped = []
    for c in components:
        caps = set(c.inferred_capabilities)
        forms = []
        if c.kind in ("python_function", "python_class", "code_file"):
            forms.append(MappedForm(_new_id(), c.id, "snippet_pack", f"Reusable {c.kind} `{c.name}`", "developers", "Bundle into paid pack"))
        if "automation_bot" in caps or "scheduler" in caps:
            forms.append(MappedForm(_new_id(), c.id, "cli_tool", f"CLI tool based on `{c.name}`", "power users", "Polish into CLI"))
        if "documentation" in caps or "teachable" in caps:
            forms.append(MappedForm(_new_id(), c.id, "mini_course_module", f"Lesson from `{c.name}`", "learners", "Mini-course module"))
        if not forms:
            forms.append(MappedForm(_new_id(), c.id, "asset", f"General asset `{c.name}`", "broad", "Evaluate for bundles"))
        mapped.extend(forms)
    return mapped

def score_forms(mapped_forms: List[MappedForm], components: List[Component]) -> List[ScoredForm]:
    comp_index = {c.id: c for c in components}
    scored = []
    for mf in mapped_forms:
        c = comp_index.get(mf.component_id)
        v = 0.5
        e = 0.5
        u = 0.5
        if c and ("documentation" in c.inferred_capabilities or "teachable" in c.inferred_capabilities):
            v += 0.4
        if mf.form_type in ("mini_course_module", "cli_tool"):
            v += 0.3
        scored.append(ScoredForm(_new_id(), mf.id, max(0, min(1, v)), max(0, min(1, e)), max(0, min(1, u))))
    return scored

def build_execution_plan(components: List[Component], mapped_forms: List[MappedForm], scored_forms: List[ScoredForm]) -> ExecutionPlan:
    mf_index = {mf.id: mf for mf in mapped_forms}
    ranked = sorted(scored_forms, key=lambda s: (-(s.value_score + s.uniqueness_score), s.effort_score))
    items = []
    seen = set()
    for sf in ranked:
        mf = mf_index[sf.mapped_form_id]
        c = next((c for c in components if c.id == mf.component_id), None)
        if not c or c.id in seen: continue
        seen.add(c.id)
        tier = "high" if sf.value_score >= 0.7 else "medium" if sf.value_score >= 0.4 else "low"
        items.append(ExecutionItem(
            title=f"{mf.form_type}: {c.name}",
            description=mf.description,
            actions=["Extract component", f"Build {mf.form_type}", "Add documentation", "Package for sale"],
            estimated_effort_hours=8.0,
            projected_value_tier=tier
        ))
    nodes = [{"id": c.id, "label": c.name, "kind": c.kind, "path": c.path} for c in components]
    return ExecutionPlan(components, mapped_forms, scored_forms, items, {"nodes": nodes, "edges": []})

def plan_to_markdown(plan: ExecutionPlan) -> str:
    lines = ["# SALVAGEBOTX™ — No Mercy Code Recycler & Productization Machine\n\n"]
    lines.append("## Quick Rebuild & Glue Ideas\nUse these immediately.\n\n")
    lines.append("## Course & Education Candidates\n")
    for item in plan.prioritized_items[:5]:
        lines.append(f"### {item.title}")
        lines.append(f"**{item.projected_value_tier.upper()}** — ~{item.estimated_effort_hours:.1f} hours")
        lines.append(f"{item.description}\n")
        for a in item.actions:
            lines.append(f"• {a}")
        lines.append("")
    lines.append("## All Prioritized Ideas\n")
    for item in plan.prioritized_items:
        lines.append(f"### {item.title}")
        lines.append(f"**{item.projected_value_tier.upper()}** — ~{item.estimated_effort_hours:.1f} hours")
        lines.append(f"{item.description}\n")
        for a in item.actions:
            lines.append(f"• {a}")
        lines.append("")
    return "\n".join(lines)

def plan_to_json(plan: ExecutionPlan) -> Dict[str, Any]:
    return asdict(plan)

async def run_pipeline(source: str, kind: str, branch: Optional[str] = None, language_hint: str = "txt", output_dir: Optional[str] = None):
    result = await ingest(source, kind, branch, language_hint)
    logger.info(f"SalvageBotX™ ingested {result.root_path}")

    components = decompose(result)
    components = classify_components(components)
    forms = map_to_products(components)
    scored = score_forms(forms, components)
    plan = build_execution_plan(components, forms, scored)

    out_dir = Path(output_dir).resolve() if output_dir else result.root_path
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "SALVAGEBOTX_PLAN.md").write_text(plan_to_markdown(plan), encoding="utf-8")
    (out_dir / "salvagebotx_plan.json").write_text(json.dumps(plan_to_json(plan), indent=2), encoding="utf-8")

    logger.info("✅ SALVAGEBOTX™ finished")
    logger.info(f"Plan saved to {out_dir}")

def main():
    import argparse
    p = argparse.ArgumentParser(description="SALVAGEBOTX™ — The No Mercy Code Recycler and Productization Machine")
    p.add_argument("source", help="Path or URL")
    p.add_argument("--kind", choices=["local","git","zip","pasted"], default="local")
    p.add_argument("--branch")
    p.add_argument("--language-hint", default="txt")
    p.add_argument("--output-dir")
    args = p.parse_args()
    asyncio.run(run_pipeline(args.source, args.kind, args.branch, args.language_hint, args.output_dir))

if __name__ == "__main__":
    main()
