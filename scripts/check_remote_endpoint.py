"""One structured call through the real pipeline path, against any
OpenAI-compatible endpoint -- verification for a newly-stood-up remote
(e.g. Lyceum) before trusting it with a real cascade run.

Reuses `structured_completion()` directly, so this exercises the exact same
`instructor` + JSON-mode path Step A/B/C use in production, not a parallel
reimplementation. No project data touched, nothing written to disk.

TRIFECTA_REMOTE_* in model_compare.env is NOT read by any code in this repo
(checked 6 Nov 2026) -- pass --base-url/--model/--api-key explicitly, or
export the generic OLLAMA_BASE_URL/TRIFECTA_MODEL/TRIFECTA_API_KEY that
`trifecta_annotation.config` already reads.

Usage:
    python scripts/check_remote_endpoint.py \
        --base-url https://api.lyceum.technology/api/v2/external \
        --model 06169012-beae-4add-b96e-435d2d9bf542 \
        --api-key "$LYCEUM_API_KEY"

    # or, with env vars already exported:
    python scripts/check_remote_endpoint.py
"""

from __future__ import annotations

import argparse
import time

from pydantic import BaseModel

from trifecta_annotation.llm import structured_completion


class _PingResponse(BaseModel):
    ready: bool
    note: str


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", help="Overrides OLLAMA_BASE_URL for this call only")
    parser.add_argument("--model", help="Overrides TRIFECTA_MODEL for this call only")
    parser.add_argument("--api-key", help="Overrides TRIFECTA_API_KEY for this call only")
    args = parser.parse_args()

    kwargs = {}
    if args.base_url:
        kwargs["base_url"] = args.base_url
    if args.model:
        kwargs["model"] = args.model
    # structured_completion has no api_key param (it goes through
    # make_instructor_client's default resolution), so honor --api-key by
    # setting the env var that trifecta_api_key() reads, for this process only.
    if args.api_key:
        import os
        os.environ["TRIFECTA_API_KEY"] = args.api_key

    print(f"base_url : {args.base_url or '(from OLLAMA_BASE_URL / default)'}")
    print(f"model    : {args.model or '(from TRIFECTA_MODEL / default)'}")

    t0 = time.monotonic()
    try:
        result = structured_completion(
            _PingResponse,
            system_prompt="You are a connectivity check. Respond only in the given schema.",
            user_prompt="Set ready=true and note to the exact string 'pong'.",
            **kwargs,
        )
    except Exception as exc:  # noqa: BLE001 -- this IS the error-reporting path
        elapsed = time.monotonic() - t0
        print(f"FAILED after {elapsed:.1f}s: {type(exc).__name__}: {exc}")
        raise SystemExit(1)

    elapsed = time.monotonic() - t0
    print(f"OK in {elapsed:.1f}s -> ready={result.ready} note={result.note!r}")
    if not result.ready or result.note != "pong":
        print("WARNING: endpoint responded but did not follow the instruction exactly "
              "-- check model/prompt compatibility before trusting a real batch run.")


if __name__ == "__main__":
    main()
