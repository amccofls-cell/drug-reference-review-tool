from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen


MFDS_LIST_URL = "https://apis.data.go.kr/1471000/DrugPrdtPrmsnInfoService07/getDrugPrdtPrmsnInq07"
MFDS_DETAIL_URL = "https://apis.data.go.kr/1471000/DrugPrdtPrmsnInfoService07/getDrugPrdtPrmsnDtlInq06"
HIRA_PRICE_URL = "https://apis.data.go.kr/B551182/dgamtCrtrInfoService1.2/getDgamtList"


def _digits(value: Any) -> str:
    return re.sub(r"\D", "", "" if value is None else str(value))


def extract_barcode_key(value: Any) -> str:
    """Return MFDS BAR_CODE positions 4-11 (1-based), an 8-digit product key."""
    digits = _digits(value)
    return digits[3:11] if len(digits) >= 11 else ""


def extract_mdscd_key(value: Any) -> str:
    """Return the first eight digits of a HIRA mdsCd."""
    digits = _digits(value)
    return digits[:8] if len(digits) >= 8 else ""


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = html.unescape(str(value)).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def document_text(value: Any) -> str:
    """Preserve official document meaning while removing XML/HTML transport markup."""
    if not value:
        return ""
    raw = html.unescape(str(value)).strip()
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return normalize_text(re.sub(r"<[^>]+>", " ", raw))
    parts: list[str] = []
    for node in root.iter():
        title = node.attrib.get("title")
        if title:
            parts.append(title)
        if node.text and node.text.strip():
            parts.append(node.text)
    return normalize_text(" ".join(parts))


def _parse_date(value: Any) -> date | None:
    digits = _digits(value)
    if len(digits) < 8:
        return None
    try:
        return datetime.strptime(digits[:8], "%Y%m%d").date()
    except ValueError:
        return None


def _is_deleted(row: dict[str, Any]) -> bool:
    values = [row.get("payTpNm"), row.get("status"), row.get("delYn")]
    return any(normalize_text(v).lower() in {"삭제", "deleted", "y"} for v in values if v is not None)


def select_effective_price(rows: Iterable[dict[str, Any]], as_of: date) -> dict[str, Any] | None:
    """Select the latest HIRA price effective on *as_of*.

    A row is effective when adtStaDd <= as_of and sellEptDd is absent or not
    earlier than as_of. Among eligible rows, the latest start date wins.
    """
    eligible: list[tuple[date, dict[str, Any]]] = []
    for row in rows:
        if _is_deleted(row):
            continue
        start = _parse_date(row.get("adtStaDd"))
        end = _parse_date(row.get("sellEptDd"))
        if start is None or start > as_of:
            continue
        if end is not None and end < as_of:
            continue
        eligible.append((start, row))
    if not eligible:
        return None
    eligible.sort(key=lambda pair: pair[0], reverse=True)
    return eligible[0][1]


def _items_from_text(raw: str) -> list[dict[str, Any]]:
    raw = raw.strip()
    if raw.startswith("<"):
        root = ET.fromstring(raw)
        code = root.findtext(".//resultCode")
        if code and code != "00":
            raise RuntimeError(root.findtext(".//resultMsg") or f"API error {code}")
        return [
            {child.tag: child.text or "" for child in item}
            for item in root.findall(".//items/item")
        ]
    data = json.loads(raw)
    body = data.get("body", data.get("response", {}).get("body", {}))
    items = body.get("items", []) if isinstance(body, dict) else []
    if isinstance(items, dict):
        items = items.get("item", items)
    if isinstance(items, dict):
        items = [items]
    return list(items or [])


@dataclass
class ApiClient:
    mfds_key: str
    hira_key: str
    timeout: int = 30
    def _get(self, url: str, key: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        query = {"serviceKey": key, "type": "json", **params}
        request = Request(f"{url}?{urlencode(query)}", headers={"User-Agent": "drug-review-reference/0.1"})
        with urlopen(request, timeout=self.timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            raw = response.read().decode(charset, errors="replace")
        return _items_from_text(raw)

    def search_mfds(self, query: str, rows: int = 100) -> list[dict[str, Any]]:
        return self._get(MFDS_LIST_URL, self.mfds_key, {"item_name": query, "numOfRows": rows, "pageNo": 1})

    def mfds_detail(self, item_seq: str) -> dict[str, Any]:
        items = self._get(MFDS_DETAIL_URL, self.mfds_key, {"item_seq": item_seq})
        if not items:
            raise LookupError(f"MFDS detail not found: {item_seq}")
        return items[0]

    def hira_rows(self, *, mds_cd: str | None = None, item_name: str | None = None) -> list[dict[str, Any]]:
        if not mds_cd and not item_name:
            raise ValueError("mds_cd or item_name is required")
        params = {"mdsCd": mds_cd} if mds_cd else {"itmNm": item_name}
        return self._get(HIRA_PRICE_URL, self.hira_key, params)


def _mfds_reference(detail: dict[str, Any]) -> dict[str, Any]:
    return {
        "item_seq": normalize_text(detail.get("ITEM_SEQ")),
        "product_name": normalize_text(detail.get("ITEM_NAME")),
        "manufacturer": normalize_text(detail.get("ENTP_NAME")),
        "barcode": normalize_text(detail.get("BAR_CODE")),
        "product_key_8": extract_barcode_key(detail.get("BAR_CODE")),
        "ingredient": normalize_text(detail.get("MAIN_ITEM_INGR") or detail.get("INGR_NAME")),
        "dosage_form": normalize_text(detail.get("FORM_CODE_NAME") or detail.get("CHART")),
        "package_unit": normalize_text(detail.get("PACK_UNIT")),
        "indications_original": str(detail.get("EE_DOC_DATA") or ""),
        "indications_text": document_text(detail.get("EE_DOC_DATA")),
        "dosage_original": str(detail.get("UD_DOC_DATA") or ""),
        "dosage_text": document_text(detail.get("UD_DOC_DATA")),
        "precautions_original": str(detail.get("NB_DOC_DATA") or ""),
        "precautions_text": document_text(detail.get("NB_DOC_DATA")),
        "storage": normalize_text(detail.get("STORAGE_METHOD")),
    }


def build_reference_bundle(client: ApiClient, detail: dict[str, Any], as_of: date) -> dict[str, Any]:
    mfds = _mfds_reference(detail)
    key8 = mfds["product_key_8"]
    price_rows = client.hira_rows(mds_cd=key8) if key8 else []
    exact_rows = [row for row in price_rows if extract_mdscd_key(row.get("mdsCd")) == key8]
    selected = select_effective_price(exact_rows, as_of) if key8 else None
    match_status = "matched_by_product_key_8" if selected else "unmatched"
    hira = None
    if selected:
        hira = {
            "mds_cd": normalize_text(selected.get("mdsCd")),
            "product_key_8": extract_mdscd_key(selected.get("mdsCd")),
            "product_name": normalize_text(selected.get("itmNm")),
            "manufacturer": normalize_text(selected.get("mnfEntpNm")),
            "max_price": selected.get("mxCprc"),
            "effective_start": normalize_text(selected.get("adtStaDd")),
            "sale_end": normalize_text(selected.get("sellEptDd")),
        }
    return {
        "schema_version": "1.0",
        "reference_date": as_of.isoformat(),
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "match": {"status": match_status, "key": key8 or None},
        "mfds": mfds,
        "hira": hira,
        "warnings": [] if selected else ["현재 기준일에 유효한 8자리 제품코드 일치 약가를 확인하지 못함"],
    }


def dump_bundle(bundle: dict[str, Any], path: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(bundle, handle, ensure_ascii=False, indent=2)
