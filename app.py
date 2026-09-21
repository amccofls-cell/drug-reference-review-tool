from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from drug_reference.core import ApiClient, build_reference_bundle  # noqa: E402


def _secret(name: str) -> str:
    """Read a deployment secret, falling back to an environment variable."""
    try:
        value = st.secrets.get(name, "")
    except (FileNotFoundError, KeyError):
        value = ""
    return str(value or os.environ.get(name, "")).strip()


st.set_page_config(
    page_title="의약품 공식 레퍼런스 생성",
    page_icon="💊",
    layout="wide",
)

st.title("의약품 공식 레퍼런스 생성")
st.caption("식약처 허가사항과 심평원 급여약가를 제품코드로 연결해 검토용 JSON을 만듭니다.")

mfds_key = _secret("MFDS_API_KEY")
hira_key = _secret("HIRA_API_KEY")
if not mfds_key or not hira_key:
    st.error("배포 설정의 Secrets에 MFDS_API_KEY와 HIRA_API_KEY를 등록해 주세요.")
    st.stop()

with st.form("reference_form"):
    item_seq = st.text_input(
        "식약처 품목기준코드 (ITEM_SEQ)",
        placeholder="예: 200000000",
        help="의약품안전나라 품목기준코드를 입력합니다.",
    ).strip()
    as_of = st.date_input("약가 기준일", value=date.today())
    submitted = st.form_submit_button("공식 레퍼런스 조회", type="primary")

if submitted:
    if not item_seq:
        st.warning("품목기준코드를 입력해 주세요.")
        st.stop()

    client = ApiClient(mfds_key=mfds_key, hira_key=hira_key)
    try:
        with st.spinner("식약처 허가사항과 심평원 약가를 조회하고 있습니다..."):
            detail = client.mfds_detail(item_seq)
            bundle = build_reference_bundle(client, detail, as_of)
    except Exception as exc:
        st.error(f"공식자료 조회에 실패했습니다: {exc}")
        st.stop()

    mfds = bundle["mfds"]
    hira = bundle["hira"]
    st.success("공식 레퍼런스를 생성했습니다.")

    col1, col2, col3 = st.columns(3)
    col1.metric("제품명", mfds.get("product_name") or "확인되지 않음")
    col2.metric("제조사", mfds.get("manufacturer") or "확인되지 않음")
    col3.metric("현재 약가", f'{hira["max_price"]:,}원' if hira and isinstance(hira.get("max_price"), (int, float)) else (str(hira.get("max_price")) + "원" if hira and hira.get("max_price") not in (None, "") else "매칭되지 않음"))

    if bundle["warnings"]:
        for warning in bundle["warnings"]:
            st.warning(warning)

    with st.expander("허가사항 및 약가 요약", expanded=True):
        st.write({
            "품목기준코드": mfds.get("item_seq"),
            "제품코드 8자리": mfds.get("product_key_8"),
            "성분": mfds.get("ingredient"),
            "제형": mfds.get("dosage_form"),
            "보관방법": mfds.get("storage"),
            "심평원 제품코드": hira.get("mds_cd") if hira else None,
            "약가 적용 시작일": hira.get("effective_start") if hira else None,
            "판매 종료일": hira.get("sale_end") if hira else None,
        })

    json_text = json.dumps(bundle, ensure_ascii=False, indent=2)
    st.download_button(
        "검토용 JSON 다운로드",
        data=json_text.encode("utf-8"),
        file_name=f"drug_reference_{item_seq}_{as_of.isoformat()}.json",
        mime="application/json",
    )
    with st.expander("JSON 미리보기"):
        st.json(bundle)
