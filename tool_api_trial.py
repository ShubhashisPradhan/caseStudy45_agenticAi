"""
Local mock tool implementations + a thin runtime adapter that makes them callable .

Usage in  driver (pseudo):
    from tools_runtime import call_tool

    fc = msg["function_call"]  # {"name": "...", "arguments": "<json or dict>"}
    fn_msg = call_tool(fc["name"], fc.get("arguments", {}))
    messages.append(fn_msg)  # {"role": "function", "name": <tool>, "content": "<json str>"}
"""

from __future__ import annotations
from typing import Dict, Any, Callable, Mapping
import json
import inspect

# ------------------------- Mock tool implementations -------------------------

def pipedrive_list_deals(filter_id: str, status: str, limit: str, **_) -> Dict[str, Any]:
    """Calls GET /api/v2/deals. Inputs: filter_id, status, limit. Outputs: deals list (id, title, org_id, status)."""
    return {
        "success": True,
        "data": {
            "deals": [
                {"id": 101, "title": "Cost Reduction Initiative - Globex Corp", "org_id": "Globex Corp", "status": "won"}
            ]
        }
    }

def tableau_list_workbooks(*, api_version: str = None, site_id: str = None, **_) -> Dict[str, Any]:
    """
    Calls GET /api/{api-version}/sites/{site-id}/workbooks.
    Accepts either api_version/site_id or hyphenated aliases via kwargs.
    """
    # Hyphenated aliases from schema
    api_version = api_version or _ .get("api-version")
    site_id    = site_id    or _ .get("site-id")
    return {
        "workbooks": [
            {"id": "wb_pre",  "name": "Globex Financials - Pre Cost Cut",  "createdAt": "2023-12-31T00:00:00Z"},
            {"id": "wb_post", "name": "Globex Financials - Post Cost Cut", "createdAt": "2024-06-30T00:00:00Z"}
        ]
    }

def confluence_list_pages(*, limit: int, spaceId: str, title: str, **_) -> Dict[str, Any]:
    """Calls GET /wiki/api/v2/pages. Inputs: limit, spaceId, title. Outputs: results (id,title,status)."""
    return {
        "results": [
            {"id": "p001", "status": "current", "title": "Globex Cost-Cutting Strategies", "spaceId": spaceId}
        ],
        "_links": {"next": None, "base": "https://confluence.example.com"}
    }

def google_analytics_4_run_report(*, propertyId: str, request: Dict[str, Any], **_) -> Dict[str, Any]:
    """Calls POST /v1beta/properties/{propertyId}:runReport. Inputs: propertyId, request (metrics/dateRanges)."""
    return {
        "report": {
            "dimensionHeaders": [{"name": "dateRange"}],
            "metricHeaders": [{"name": "totalRevenue"}],
            "rows": [
                {"dimensionValues": [{"value": "pre_cut"}],  "metricValues": [{"value": "1250000"}]},
                {"dimensionValues": [{"value": "post_cut"}], "metricValues": [{"value": "1480000"}]},
            ],
            "rowCount": 2
        }
    }

def analyze_financial_impact(*, caseStudyId: str, preRevenue: int, postRevenue: int, **_) -> Dict[str, Any]:
    """Compute absolute & % increase with brief insight. Inputs: caseStudyId, preRevenue, postRevenue."""
    abs_increase = int(postRevenue) - int(preRevenue)
    pct_increase = round((abs_increase / int(preRevenue)) * 100, 1) if preRevenue else 0.0
    return {
        "absoluteIncrease": abs_increase,
        "percentIncrease": pct_increase,
        "efficiencyInsight": "Post-cut operations generated more revenue with a leaner cost base.",
        "rating": "positive"
    }

def writer_generate_text(*, model: str, prompt: str, max_tokens: int = 420, **_) -> Dict[str, Any]:
    """POST /v1/completions. Inputs: model, prompt, max_tokens, temperature, top_p, stop, best_of, random_seed, stream."""
    title_line = "Globex Corp Cost-Cutting Success Story"
    footer = "© 2024 Globex Corp. All rights reserved. For authorised distribution only."
    md = f"# {title_line}\n\n"
    md += "## Executive Summary\n"
    md += ("Facing rising costs and flat growth, Globex Corp launched an efficiency program "
           "focused on vendor renegotiation, 60% cloud migration, invoice automation and "
           "retirement of non-profitable products. Within six months, revenue rose from "
           "$1,250,000 to $1,480,000 (+18.4%, +$230,000) alongside improved operational efficiency.\n\n")
    md += "## Challenges\n- Fragmented supplier contracts\n- Legacy on-prem infrastructure\n- Manual finance workflows\n\n"
    md += "## Strategy\n1. Supplier contract renegotiation\n2. 60% cloud migration\n3. Invoice-processing automation\n4. Retirement of non-profitable products\n\n"
    md += "## Implementation\n- Procurement achieved ~12% reduction across top-10 suppliers\n- Phased cloud migrations completed; on-prem footprint reduced\n- RPA for invoice entry cut cycle time from 4 days to ~8 hours (≈-83%)\n\n"
    md += "## Results & Impact\n"
    md += "| Metric | Pre-Cut | Post-Cut | Change |\n|---|---|---|---|\n"
    md += "| Total Revenue | $1,250,000 | $1,480,000 | +18.4% (+$230,000) |\n"
    md += "| Supplier Spend | – | –12% |  |\n"
    md += "| Invoice Cycle Time | 4 days | 8 hours | –83% |\n\n"
    md += "## Visual References\n- Tableau: wb_pre, wb_post\n- Confluence: p001\n\n"
    md += "## Conclusion & Next Steps\nExtending automation and establishing quarterly vendor performance reviews will help sustain savings and support growth.\n\n"
    md += f"---\n{footer}\n"
    return {"text": md}

# ------------------------- Runtime adapter / dispatcher -------------------------

# Map tool name -> python function
_TOOL_REGISTRY: Dict[str, Callable[..., Dict[str, Any]]] = {
    "pipedrive_list_deals": pipedrive_list_deals,
    "tableau_list_workbooks": tableau_list_workbooks,
    "confluence_list_pages": confluence_list_pages,
    "google_analytics_4_run_report": google_analytics_4_run_report,
    "analyze_financial_impact": analyze_financial_impact,
    "writer_generate_text": writer_generate_text,
}

# Per-tool key aliases to normalize incoming JSON -> function kwarg names
_KEY_ALIASES: Dict[str, Mapping[str, str]] = {
    # schema → function kwarg
    "tableau_list_workbooks": {"api-version": "api_version", "site-id": "site_id"},
    # keep others identity; add here if schemas differ from python kwargs
}

# Basic type coercions for common keys
_INT_KEYS = {
    "limit", "preRevenue", "postRevenue", "max_tokens", "best_of", "random_seed",
}
_FLOAT_KEYS = {"temperature", "top_p"}
_BOOL_KEYS = {"stream"}

def _parse_arguments(raw_args: Any) -> Dict[str, Any]:
    """Accept JSON string or dict and return a dict."""
    if raw_args is None:
        return {}
    if isinstance(raw_args, str):
        raw_args = raw_args.strip()
        return json.loads(raw_args) if raw_args else {}
    if isinstance(raw_args, dict):
        return dict(raw_args)
    raise TypeError(f"Unsupported arguments type: {type(raw_args)}")

def _normalize_keys(tool: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Apply per-tool key aliasing and hyphen→underscore fallback."""
    out = {}
    aliases = _KEY_ALIASES.get(tool, {})
    for k, v in args.items():
        # exact alias mapping first
        if k in aliases:
            out[aliases[k]] = v
            continue
        # generic: turn hyphen-case to snake_case
        if "-" in k and k.replace("-", "_") not in out:
            out[k.replace("-", "_")] = v
            continue
        out[k] = v
    return out

def _coerce_types(args: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for k, v in args.items():
        if v is None:
            out[k] = v
            continue
        try:
            if k in _INT_KEYS:
                out[k] = int(v)
            elif k in _FLOAT_KEYS:
                out[k] = float(v)
            elif k in _BOOL_KEYS:
                if isinstance(v, bool):
                    out[k] = v
                elif isinstance(v, str):
                    out[k] = v.strip().lower() in {"1", "true", "yes", "y"}
                else:
                    out[k] = bool(v)
            else:
                out[k] = v
        except Exception:
            # If coercion fails, keep original; the callee may still handle it
            out[k] = v
    return out

def _filter_kwargs(fn: Callable[..., Any], kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Drop keys the function doesn't accept (but keep **kwargs in signature)."""
    sig = inspect.signature(fn)
    params = sig.parameters
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
        # function accepts **kwargs → pass all
        return kwargs
    # otherwise only pass known parameters
    allowed = set(params.keys())
    return {k: v for k, v in kwargs.items() if k in allowed}

def call_tool(name: str, raw_args: Any) -> Dict[str, Any]:
    """
    Dispatch a tool by name with raw JSON/dict arguments.
    Returns a ready-to-append function message:
        {"role":"function","name": name,"content": "<json str>"}
    """
    if name not in _TOOL_REGISTRY:
        content = json.dumps({"error": f"Unknown tool: {name}"})
        return {"role": "function", "name": name, "content": content}

    fn = _TOOL_REGISTRY[name]
    try:
        args = _parse_arguments(raw_args)
        args = _normalize_keys(name, args)
        args = _coerce_types(args)
        kwargs = _filter_kwargs(fn, args)

        result = fn(**kwargs)  # call the actual mock tool
        # Must be JSON-serializable
        content = json.dumps(result)
        return {"role": "function", "name": name, "content": content}
    except Exception as e:
        # Fail safe: return error payload (still a valid function message)
        content = json.dumps({"error": f"{type(e).__name__}: {e}"})
        return {"role": "function", "name": name, "content": content}

# ------------------------- Optional: quick self-test -------------------------
if __name__ == "__main__":
    print(call_tool("pipedrive_list_deals", {"filter_id": "cost_cutting_success", "status": "won", "limit": "5"}))
    print(call_tool("tableau_list_workbooks", '{"api-version":"3.18","site-id":"globex_fin"}'))
    print(call_tool("confluence_list_pages", {"limit": 10, "spaceId": "COSTCUT", "title": "Cost Cutting Strategy"}))
    print(call_tool("google_analytics_4_run_report", {"propertyId":"GA4_GLOBEX","request":{"metrics":[{"name":"totalRevenue"}]}}))
    print(call_tool("analyze_financial_impact", {"caseStudyId":"CASESTUDY_COSTCUTTING_20240705","preRevenue":1250000,"postRevenue":1480000}))
    print(call_tool("writer_generate_text", {"model": "palmyra-x5", "prompt": "Write it", "max_tokens": 420}))
