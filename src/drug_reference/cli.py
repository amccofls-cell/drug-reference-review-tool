from __future__ import annotations

import argparse
import json
import os
from datetime import date
from pathlib import Path

from .core import ApiClient, build_reference_bundle, dump_bundle


def main() -> None:
    parser = argparse.ArgumentParser(description="식약처·심평원 공식 레퍼런스 생성")
    parser.add_argument("--item-seq", required=True, help="식약처 품목기준코드")
    parser.add_argument("--as-of", default=date.today().isoformat(), help="약가 기준일 YYYY-MM-DD")
    parser.add_argument("--output", required=True, help="출력 JSON 경로")
    args = parser.parse_args()

    mfds_key = os.environ.get("MFDS_API_KEY", "")
    hira_key = os.environ.get("HIRA_API_KEY", "")
    if not mfds_key or not hira_key:
        parser.error("MFDS_API_KEY와 HIRA_API_KEY 환경변수가 필요합니다")
    as_of = date.fromisoformat(args.as_of)
    client = ApiClient(mfds_key=mfds_key, hira_key=hira_key)
    detail = client.mfds_detail(args.item_seq)
    bundle = build_reference_bundle(client, detail, as_of)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    dump_bundle(bundle, args.output)
    print(json.dumps({"output": args.output, "match": bundle["match"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

