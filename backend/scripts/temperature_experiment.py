"""Run the same prompt at temperature 0.0 / 0.5 / 1.0 against YOUR local Ollama and write docs/PROMPT_EXPERIMENTS.md.

python scripts/temperature_experiment.py sample_docs/meeting_notes.txt --runs 2
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import get_settings  # noqa: E402
from app.db.session import init_db  # noqa: E402
from app.llm.client import OllamaClient, complete  # noqa: E402
from app.llm.options import GenParams  # noqa: E402
from app.services.engine import SYSTEM  # noqa: E402
from app.services.prompt_store import PromptStore  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("file", help="path relative to DOCS_ROOT")
ap.add_argument("--runs", type=int, default=2)
ap.add_argument("--prompt", default="summarize_short")
args = ap.parse_args()


async def main() -> None:
    s = get_settings()
    init_db(s.db_path)
    from app.core.extractors import extract

    text = extract(s.docs_root / args.file).text
    prompt = PromptStore(s).render(args.prompt, None, {"text": text, "style": "short"})
    llm = OllamaClient(s)
    lines = [f"# Temperature experiment\n\nModel `{s.ollama_model}` · prompt `{args.prompt}` · file `{args.file}`\n"]
    for temp in (0.0, 0.5, 1.0):
        lines.append(f"\n## temperature = {temp}\n")
        for i in range(1, args.runs + 1):
            out, usage = await complete(
                llm,
                [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
                GenParams(temperature=temp, max_tokens=200),
            )
            lines.append(f"**Run {i}** ({usage.tokens_out} tokens)\n\n> " + out.strip().replace("\n", "\n> ") + "\n")
    out_path = Path(__file__).resolve().parents[2] / "docs" / "PROMPT_EXPERIMENTS.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print("wrote", out_path)


asyncio.run(main())
