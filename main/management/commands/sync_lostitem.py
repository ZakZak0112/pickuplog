# pickuplog/main/management/commands/sync_lostitem_file.py

import pandas as pd
from django.core.management.base import BaseCommand
from django.utils.timezone import make_aware
from datetime import datetime
from pathlib import Path
from main.models import LostItem # LostItem 모델 임포트

# --- Helper Functions 및 Mapping (제시된 코드 그대로 유지) ---

# 한글 헤더 -> 영문 표준 헤더 매핑
COLMAP_KO2EN = {
    "분실물SEQ": "item_id",
    "분실물상태": "status",
    "등록일자": "registered_at",
    "수령일자": "received_at",
    "유실물상세내용": "description",
    "보관장소": "storage_location",
    "분실물등록자ID": "registrar_id",
    "분실물명": "item_name",
    "분실물종류": "category",
    "수령위치(회사)": "pickup_company_location",
    "조회수": "views",
    # (transport, line, station은 CSV에 있다면 자동 매핑되거나 기본값 사용을 위해 여기에 추가하지 않습니다)
}

def norm_status(v: str) -> str:
    s = ("" if pd.isna(v) else str(v)).strip()
    if s in ("수령", "수령완료", "회수", "claimed", "returned"):
        # 프로젝트 표준 상태: 수령은 'claimed' 또는 'received'
        return "claimed" 
    if s in ("폐기", "폐기/기타", "discarded"):
        return "discarded"
    return "registered"

def to_aware_dt(v):
    """문자열/엑셀시리얼 → aware datetime. '00:00.0' 같은 값은 None 처리."""
    if pd.isna(v):
        return None
    s = str(v).strip()
    if s in ("", "00:00.0", "0:00:00", "00:00", "0"):
        return None
    # errors="coerce"로 파싱 실패시 NaT(Not a Time) 반환
    ts = pd.to_datetime(v, errors="coerce") 
    if pd.isna(ts):
        return None
    if ts.tzinfo is None:
        return make_aware(ts.to_pydatetime())
    return ts.to_pydatetime()

def read_file_auto(path: Path):
    # 확장자 기준: xlsx면 read_excel, 그 외는 csv로 시도 (인코딩 순차)
    if path.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(path)
    # CSV: utf-8 -> cp949 -> ISO-8859-1 순차 시도
    for enc in ("utf-8", "cp949", "ISO-8859-1"):
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError:
            continue
    # 그래도 실패 시, 대체 문자로라도 읽기
    return pd.read_csv(path, encoding="utf-8", errors="replace")

class Command(BaseCommand):
    # 커맨드 이름이 'sync_lostitem_file'로 인식됩니다.
    help = "CSV/XLSX에서 분실물 데이터를 불러와 LostItem에 upsert합니다."

    def add_arguments(self, parser):
        parser.add_argument("file_path", type=str, help="CSV 또는 XLSX 파일 경로")

    def handle(self, *args, **opts):
        self.stdout.write(self.style.MIGRATE_HEADING("로컬 파일 기반 LostItem 적재 시작"))
        p = Path(opts["file_path"]).expanduser()
        if not p.exists():
            self.stderr.write(self.style.ERROR(f"❌ 파일이 없습니다: {p}"))
            return

        df = read_file_auto(p)

        # 한글 헤더일 경우 영문으로 변경
        if set(COLMAP_KO2EN.keys()) & set(df.columns):
            df = df.rename(columns=COLMAP_KO2EN)

        # 필수 컬럼 존재 확인
        if "item_id" not in df.columns:
            self.stderr.write(self.style.ERROR("❌ 'item_id'(=분실물SEQ) 컬럼을 찾을 수 없습니다. 헤더를 확인하세요."))
            self.stderr.write(f"현재 컬럼: {list(df.columns)}")
            return

        created, updated, skipped = 0, 0, 0

        for _, r in df.iterrows():
            item_id = str(r.get("item_id") or "").strip()
            if not item_id:
                skipped += 1
                continue

            status = norm_status(r.get("status"))
            reg_at = to_aware_dt(r.get("registered_at"))
            recv_at = to_aware_dt(r.get("received_at"))
            is_received = bool(recv_at) or status == "claimed"

            defaults = {
                # transport, line, station은 CSV에 없으면 None/기본값 사용
                "transport": str(r.get("transport") or "subway"), 
                "line": (r.get("line") or None),
                "station": (r.get("station") or None),
                
                "category": str(r.get("category") or "기타"),
                "item_name": str(r.get("item_name") or ""),
                "status": status,
                "is_received": is_received,
                "registered_at": reg_at,
                "received_at": recv_at,
                "description": r.get("description") or "",
                "storage_location": str(r.get("storage_location") or ""),
                "registrar_id": (r.get("registrar_id") or None),
                "pickup_company_location": str(r.get("pickup_company_location") or ""),
                "views": int(pd.to_numeric(r.get("views"), errors="coerce") or 0),
            }

            obj, was_created = LostItem.objects.update_or_create(
                item_id=item_id,
                defaults=defaults,
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"✅ 로컬 파일 적재 완료: 생성 {created}건 / 업데이트 {updated}건 / 건너뜀 {skipped}건"
        ))