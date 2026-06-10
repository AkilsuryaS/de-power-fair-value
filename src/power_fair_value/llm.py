from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

from dotenv import find_dotenv, load_dotenv

from power_fair_value.config import project_path
from power_fair_value.utils import ensure_dir, utc_now_iso


SYSTEM_PROMPT = (
    "You are an energy trading analyst. Write concise, plain-English desk notes. "
    "Use the supplied metrics only; do not invent market data."
)


def build_prompt(context: Dict[str, Any]) -> str:
    return f"""
Create a short trading memo for a DE-LU power day-ahead fair-value model.

Use this structured context:
{json.dumps(context, indent=2)}

Return Markdown with:
1. Signal summary
2. DA-to-curve positioning
3. How the view would be invalidated

Keep it under 250 words.
""".strip()


def _offline_memo(context: Dict[str, Any]) -> str:
    view = context["curve_view"]
    metrics = context["validation_metrics"]
    fv = view["fair_value"]
    edges = view["edges"]
    return "\n".join(
        [
            "## Signal Summary",
            (
                f"The improved model's all-hours validation MAE is "
                f"{metrics['improved_all_hours_mae']:.2f} EUR/MWh versus "
                f"{metrics['baseline_all_hours_mae']:.2f} EUR/MWh for the 24-hour lag baseline. "
                f"For {view['forecast_date']}, fair value is {fv['base']:.2f} EUR/MWh base "
                f"and {fv['peak']:.2f} EUR/MWh peak."
            ),
            "",
            "## DA-To-Curve Positioning",
            (
                f"Base edge is {edges['base_eur_mwh']:.2f} EUR/MWh and peak edge is "
                f"{edges['peak_eur_mwh']:.2f} EUR/MWh versus the selected prompt marks. "
                f"{view['positioning']['base']} {view['positioning']['peak']}"
            ),
            "",
            "## Invalidation",
            "Invalidate or resize if residual-load forecasts, curve marks, or fuel/carbon/outage inputs move materially before execution.",
        ]
    )


def generate_trading_memo(context: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    out_dir = project_path(config, "outputs/llm")
    ensure_dir(out_dir)
    prompt = build_prompt(context)

    provider = config["llm"].get("provider", "openai")
    model = os.getenv("OPENAI_MAIN_MODEL", config["llm"].get("model", "gpt-4.1-mini"))
    provider_used = "offline_rule_based"
    output = ""
    error = None

    if config["llm"].get("enabled", True) and provider == "openai":
        load_dotenv(find_dotenv(usecwd=True))
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            try:
                from openai import OpenAI

                client = OpenAI(api_key=api_key)
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                )
                output = response.choices[0].message.content or ""
                provider_used = "openai"
            except Exception as exc:  # pragma: no cover - depends on external service
                error = str(exc)

    if not output:
        if not config["llm"].get("allow_offline_fallback", True):
            raise RuntimeError(error or "OpenAI API key unavailable and offline fallback disabled.")
        output = _offline_memo(context)

    record = {
        "timestamp_utc": utc_now_iso(),
        "provider_requested": provider,
        "provider_used": provider_used,
        "model": model,
        "prompt": prompt,
        "output": output,
        "error": error,
    }
    with Path(out_dir / "prompt_log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")
    Path(out_dir / "trading_memo.md").write_text(output + "\n", encoding="utf-8")
    return record
