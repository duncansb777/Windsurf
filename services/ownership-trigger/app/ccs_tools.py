import datetime as dt
from typing import List, Dict, Any, Optional
import uuid

# SACSF helpers
SACSF_PURPOSE_DEFAULT = "care-coordination"


def _mask_nmi(nmi: str) -> str:
    if not nmi or len(nmi) < 4:
        return "****"
    return ("*" * (len(nmi) - 4)) + nmi[-4:]


def _now_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _sacsf_log(event: str, details: Dict[str, Any]) -> None:
    # Minimal compliant structured log
    payload = {
        "ts": _now_iso(),
        "event": event,
        "details": details,
    }
    # For this demo, print; in prod, emit to audit sink (LG-1)
    print("SACSF", payload)


class SACSFContext:
    def __init__(self, user: Optional[str] = None, purpose_of_use: Optional[str] = None):
        self.user = user or "system-demo"
        self.purpose_of_use = purpose_of_use or SACSF_PURPOSE_DEFAULT

    def authorize(self) -> None:
        # AC-1: Access control (stub): ensure a caller identity exists
        if not self.user:
            raise PermissionError("Unauthorized: missing user context")
        # Extend with role/permission checks as needed

    def log_access(self, nmi: str) -> None:
        # AC-3 & LG-1: purpose-of-use and masked identifiers
        _sacsf_log(
            "ccs.get_meter_reads.access",
            {
                "nmi_masked": _mask_nmi(nmi),
                "purpose_of_use": self.purpose_of_use,
                "caller": self.user,
            },
        )

    def log_result(self, nmi: str, count: int) -> None:
        _sacsf_log(
            "ccs.get_meter_reads.result",
            {"nmi_masked": _mask_nmi(nmi), "count": count},
        )


def _coerce_date(s: Optional[str]) -> Optional[dt.date]:
    if not s:
        return None
    return dt.date.fromisoformat(s)


def _generate_mock_reads(nmi: str, start: Optional[dt.date], end: Optional[dt.date]) -> List[Dict[str, Any]]:
    # Deterministic simple mock: monthly ACTUAL and ESTIMATE
    today = dt.date.today()
    start = start or (today.replace(day=1) - dt.timedelta(days=31))
    end = end or today
    reads: List[Dict[str, Any]] = []
    cursor = start.replace(day=1)
    while cursor <= end:
        base = (hash(nmi + cursor.isoformat()) % 1000) + 1000
        reads.append({"read_type": "ACTUAL", "date": cursor.isoformat(), "value": base})
        est_date = (cursor + dt.timedelta(days=30)).replace(day=1)
        if est_date <= end:
            reads.append({"read_type": "ESTIMATE", "date": est_date.isoformat(), "value": base + 36})
        cursor = (cursor + dt.timedelta(days=32)).replace(day=1)
    return reads


def ccs_get_meter_reads(nmi: str, from_date: Optional[str], to_date: Optional[str],
                        user: Optional[str] = None, purpose_of_use: Optional[str] = None) -> Dict[str, Any]:
    ctx = SACSFContext(user=user, purpose_of_use=purpose_of_use)
    ctx.authorize()
    ctx.log_access(nmi)

    start = _coerce_date(from_date)
    end = _coerce_date(to_date)
    if start and end and start > end:
        raise ValueError("from_date must be <= to_date")

    reads = _generate_mock_reads(nmi, start, end)
    ctx.log_result(nmi, len(reads))

    return {"reads": reads}
