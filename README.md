# 의약품 공식 레퍼런스 생성 도구

병원 약물선정위원회 비교표 검토를 위해 식품의약품안전처 허가사항과 건강보험심사평가원 급여약가를 하나의 JSON으로 만드는 1차 코어 도구입니다.

## 핵심 원칙

- 허가사항은 식약처 상세 API 원문을 함께 보존합니다.
- 제품 식별은 `BAR_CODE` 4~11번째 8자리와 `mdsCd` 앞 8자리 일치를 우선합니다.
- 약가는 기준일에 유효한 이력 중 적용시작일이 가장 최근인 값을 선택합니다.
- 코드가 일치하지 않으면 제품명만으로 약가를 확정하지 않습니다.

## 설치 및 실행

```bash
python -m pip install -e .
export MFDS_API_KEY='...'
export HIRA_API_KEY='...'
drug-reference --item-seq 000000000 --as-of 2026-09-21 --output reference.json
```

API 키는 소스나 결과 JSON에 저장하지 않습니다.

## Streamlit 배포

Streamlit Community Cloud의 **Main file path**에는 `app.py`를 지정합니다.
배포 설정의 Secrets에 아래 값을 등록합니다.

```toml
MFDS_API_KEY = "식약처 서비스키"
HIRA_API_KEY = "심평원 서비스키"
```

로컬 실행은 다음과 같습니다.

```bash
python -m pip install -e .
streamlit run app.py
```

## 출력

출력 JSON은 조회 기준일, 매칭 상태, 식약처 원문/정규화 텍스트, 심평원 현재 약가와 적용기간, 경고를 포함합니다. 이 JSON과 비교표 또는 PPT를 함께 제공하면 검토 지침에 따라 사실관계를 대조할 수 있습니다.

## 현재 범위

이 버전은 정확한 품목기준코드(`ITEM_SEQ`)가 주어진 단일 제품 조회를 우선 지원합니다. 다음 단계에서 다제품 일괄 조회, CSV 출력, 비교표/PPT 추출 및 자동 검토를 연결할 수 있습니다.
