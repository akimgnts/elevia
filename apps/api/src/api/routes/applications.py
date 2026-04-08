"""
applications.py - Applications Tracker routes (Candidatures V2)

Changelog vs V0:
  - All queries scoped by user_id (from require_auth)
  - Status enum expanded to 8 values
  - Status changes recorded in application_status_history
  - GET /applications/{offer_id}/history — history log
  - POST /applications/{offer_id}/prepare — generate CV, write apply_pack_runs row
"""

import json
import logging
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from ..deps.auth import AuthenticatedUser, require_auth
from ..schemas.applications import (
    ApplicationCreate,
    ApplicationHistoryItem,
    ApplicationHistoryResponse,
    ApplicationItem,
    ApplicationListResponse,
    ApplicationStatus,
    ApplicationUpdate,
    PrepareRequest,
    PrepareResponse,
)
from ..utils import auth_db
from ..utils.db import get_connection

logger = logging.getLogger(__name__)
router = APIRouter(tags=["applications"])

STATUS_VALUES = {s.value for s in ApplicationStatus}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Lazy import of documents module (avoids circular import at module load time)
_documents_src = Path(__file__).parent.parent.parent
if str(_documents_src) not in sys.path:
    sys.path.insert(0, str(_documents_src))


def _timing_enabled() -> bool:
    value = os.getenv("ELEVIA_DEBUG_API_TIMING", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_status(status: Optional[str]) -> Optional[str]:
    if status is None:
        return None
    if status not in STATUS_VALUES:
        raise HTTPException(status_code=400, detail={"message": "Invalid status"})
    return status


def _validate_date(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if not DATE_RE.match(value):
        raise HTTPException(
            status_code=400,
            detail={"message": "Invalid next_follow_up_date (YYYY-MM-DD)"},
        )
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={"message": "Invalid next_follow_up_date (YYYY-MM-DD)"},
        )
    return value


def _record_status_change(
    conn,
    application_id: str,
    from_status: Optional[str],
    to_status: str,
    now: str,
    note: Optional[str] = None,
) -> None:
    """Insert a status history row. Must be called before conn.commit()."""
    conn.execute(
        "INSERT INTO application_status_history "
        "(id, application_id, from_status, to_status, changed_at, note) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), application_id, from_status, to_status, now, note),
    )


def _row_to_item(row) -> ApplicationItem:
    return ApplicationItem(
        id=row["id"],
        user_id=row["user_id"],
        offer_id=row["offer_id"],
        status=row["status"],
        source=row["source"] or "manual",
        note=row["note"],
        next_follow_up_date=row["next_follow_up_date"],
        current_cv_cache_key=row["current_cv_cache_key"],
        current_letter_cache_key=row["current_letter_cache_key"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        applied_at=row["applied_at"],
        last_status_change_at=row["last_status_change_at"],
        strategy_hint=row["strategy_hint"],
    )


_SELECT_COLS = (
    "id, user_id, offer_id, status, source, note, next_follow_up_date, "
    "current_cv_cache_key, current_letter_cache_key, "
    "created_at, updated_at, applied_at, last_status_change_at, strategy_hint"
)


@router.get("/applications", response_model=ApplicationListResponse)
async def list_applications(
    current_user: AuthenticatedUser = Depends(require_auth),
) -> ApplicationListResponse:
    t0 = time.perf_counter()
    conn = get_connection()
    try:
        rows = conn.execute(
            f"SELECT {_SELECT_COLS} FROM application_tracker "
            "WHERE user_id = ? ORDER BY updated_at DESC",
            (current_user.user_id,),
        ).fetchall()
    finally:
        conn.close()

    if _timing_enabled():
        logger.info(
            "applications_timing action=list total=%s count=%s",
            int((time.perf_counter() - t0) * 1000),
            len(rows),
        )

    return ApplicationListResponse(items=[_row_to_item(r) for r in rows])


@router.get("/applications/{offer_id}/history", response_model=ApplicationHistoryResponse)
async def get_application_history(
    offer_id: str,
    current_user: AuthenticatedUser = Depends(require_auth),
) -> ApplicationHistoryResponse:
    conn = get_connection()
    try:
        app_row = conn.execute(
            "SELECT id FROM application_tracker WHERE offer_id = ? AND user_id = ?",
            (offer_id, current_user.user_id),
        ).fetchone()
        if app_row is None:
            raise HTTPException(status_code=404, detail={"message": "Application not found"})

        rows = conn.execute(
            "SELECT id, application_id, from_status, to_status, changed_at, note "
            "FROM application_status_history WHERE application_id = ? ORDER BY changed_at ASC",
            (app_row["id"],),
        ).fetchall()
    finally:
        conn.close()

    items = [
        ApplicationHistoryItem(
            id=r["id"],
            application_id=r["application_id"],
            from_status=r["from_status"],
            to_status=r["to_status"],
            changed_at=r["changed_at"],
            note=r["note"],
        )
        for r in rows
    ]
    return ApplicationHistoryResponse(items=items)


@router.get("/applications/{offer_id}", response_model=ApplicationItem)
async def get_application(
    offer_id: str,
    current_user: AuthenticatedUser = Depends(require_auth),
) -> ApplicationItem:
    t0 = time.perf_counter()
    conn = get_connection()
    try:
        row = conn.execute(
            f"SELECT {_SELECT_COLS} FROM application_tracker "
            "WHERE offer_id = ? AND user_id = ?",
            (offer_id, current_user.user_id),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail={"message": "Application not found"})

    if _timing_enabled():
        logger.info(
            "applications_timing action=get total=%s",
            int((time.perf_counter() - t0) * 1000),
        )

    return _row_to_item(row)


@router.post("/applications", response_model=ApplicationItem)
async def upsert_application(
    payload: ApplicationCreate,
    current_user: AuthenticatedUser = Depends(require_auth),
) -> JSONResponse:
    t0 = time.perf_counter()
    status = _validate_status(payload.status)
    note = payload.note
    next_follow_up_date = _validate_date(payload.next_follow_up_date)
    source = payload.source or "manual"

    now = _utc_now()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, status, created_at FROM application_tracker "
            "WHERE offer_id = ? AND user_id = ?",
            (payload.offer_id, current_user.user_id),
        ).fetchone()

        if row is None:
            app_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO application_tracker "
                "(id, user_id, offer_id, status, source, note, next_follow_up_date, "
                "created_at, updated_at, last_status_change_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    app_id,
                    current_user.user_id,
                    payload.offer_id,
                    status,
                    source,
                    note,
                    next_follow_up_date,
                    now,
                    now,
                    now,
                ),
            )
            _record_status_change(conn, app_id, None, status, now)
            conn.commit()
            logger.info(
                "application_create",
                extra={"offer_id": payload.offer_id, "status": status},
            )
            created = True
        else:
            app_id = row["id"]
            old_status = row["status"]
            status_changed = old_status != status

            update_fields = (
                "status = ?, source = COALESCE(?, source), note = ?, "
                "next_follow_up_date = ?, updated_at = ?"
            )
            params: list = [status, source, note, next_follow_up_date, now]

            if status_changed:
                update_fields += ", last_status_change_at = ?"
                params.append(now)
                if status == "applied":
                    update_fields += ", applied_at = COALESCE(applied_at, ?)"
                    params.append(now)

            params.append(payload.offer_id)
            params.append(current_user.user_id)

            conn.execute(
                f"UPDATE application_tracker SET {update_fields} "
                "WHERE offer_id = ? AND user_id = ?",
                params,
            )
            if status_changed:
                _record_status_change(conn, app_id, old_status, status, now)
            conn.commit()
            logger.info(
                "application_update",
                extra={"offer_id": payload.offer_id, "status": status},
            )
            created = False

        item_row = conn.execute(
            f"SELECT {_SELECT_COLS} FROM application_tracker "
            "WHERE offer_id = ? AND user_id = ?",
            (payload.offer_id, current_user.user_id),
        ).fetchone()
    finally:
        conn.close()

    if item_row is None:
        raise HTTPException(
            status_code=500, detail={"message": "Failed to upsert application"}
        )

    if _timing_enabled():
        logger.info(
            "applications_timing action=upsert total=%s",
            int((time.perf_counter() - t0) * 1000),
        )

    result = _row_to_item(item_row)
    return JSONResponse(
        status_code=201 if created else 200, content=result.model_dump()
    )


@router.patch("/applications/{offer_id}", response_model=ApplicationItem)
async def patch_application(
    offer_id: str,
    payload: ApplicationUpdate,
    current_user: AuthenticatedUser = Depends(require_auth),
) -> ApplicationItem:
    t0 = time.perf_counter()
    # Only fields explicitly present in the JSON body are updated.
    # This lets callers clear nullable fields (note, next_follow_up_date) by
    # sending null, while omitted fields are left untouched.
    provided = payload.model_fields_set
    if not provided:
        raise HTTPException(status_code=400, detail={"message": "No fields to update"})

    now = _utc_now()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, status FROM application_tracker WHERE offer_id = ? AND user_id = ?",
            (offer_id, current_user.user_id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail={"message": "Application not found"})

        app_id = row["id"]
        old_status = row["status"]

        # Build SET clause dynamically from provided fields only
        set_parts: list = ["updated_at = ?"]
        params: list = [now]

        new_status: Optional[str] = None
        if "status" in provided and payload.status is not None:
            new_status = _validate_status(payload.status)
            set_parts.append("status = ?")
            params.append(new_status)

        if "note" in provided:
            set_parts.append("note = ?")
            params.append(payload.note)  # null clears the field

        if "next_follow_up_date" in provided:
            validated_date = _validate_date(payload.next_follow_up_date)
            set_parts.append("next_follow_up_date = ?")
            params.append(validated_date)  # null clears the field

        if "strategy_hint" in provided:
            set_parts.append("strategy_hint = ?")
            params.append(payload.strategy_hint)  # null clears the field

        status_changed = new_status is not None and new_status != old_status
        if status_changed:
            set_parts.append("last_status_change_at = ?")
            params.append(now)
            if new_status == "applied":
                set_parts.append("applied_at = COALESCE(applied_at, ?)")
                params.append(now)

        params += [offer_id, current_user.user_id]
        conn.execute(
            "UPDATE application_tracker SET "
            + ", ".join(set_parts)
            + " WHERE offer_id = ? AND user_id = ?",
            params,
        )
        if status_changed:
            _record_status_change(conn, app_id, old_status, new_status, now)
        conn.commit()
        logger.info(
            "application_patch",
            extra={"offer_id": offer_id, "status": new_status},
        )

        item_row = conn.execute(
            f"SELECT {_SELECT_COLS} FROM application_tracker "
            "WHERE offer_id = ? AND user_id = ?",
            (offer_id, current_user.user_id),
        ).fetchone()
    finally:
        conn.close()

    if item_row is None:
        raise HTTPException(status_code=404, detail={"message": "Application not found"})

    if _timing_enabled():
        logger.info(
            "applications_timing action=patch total=%s",
            int((time.perf_counter() - t0) * 1000),
        )

    return _row_to_item(item_row)


@router.delete("/applications/{offer_id}", status_code=204)
async def delete_application(
    offer_id: str,
    current_user: AuthenticatedUser = Depends(require_auth),
) -> None:
    t0 = time.perf_counter()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM application_tracker WHERE offer_id = ? AND user_id = ?",
            (offer_id, current_user.user_id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail={"message": "Application not found"})
        conn.execute(
            "DELETE FROM application_tracker WHERE offer_id = ? AND user_id = ?",
            (offer_id, current_user.user_id),
        )
        conn.commit()
        logger.info("application_delete", extra={"offer_id": offer_id})
    finally:
        conn.close()
    if _timing_enabled():
        logger.info(
            "applications_timing action=delete total=%s",
            int((time.perf_counter() - t0) * 1000),
        )
    return None


@router.post("/applications/{offer_id}/prepare", response_model=PrepareResponse)
async def prepare_application(
    offer_id: str,
    payload: PrepareRequest,
    current_user: AuthenticatedUser = Depends(require_auth),
) -> PrepareResponse:
    """
    Generate CV + cover letter for offer, write apply_pack_runs row, and
    transition application status from 'saved' to 'cv_ready'.

    Traceability: cv_cache_key and letter_cache_key are stored in both
    apply_pack_runs and application_tracker.current_{cv,letter}_cache_key.
    """
    warnings: List[str] = []
    now = _utc_now()

    # 1. Resolve or create the application
    conn = get_connection()
    try:
        app_row = conn.execute(
            f"SELECT {_SELECT_COLS} FROM application_tracker "
            "WHERE offer_id = ? AND user_id = ?",
            (offer_id, current_user.user_id),
        ).fetchone()

        if app_row is None:
            app_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO application_tracker "
                "(id, user_id, offer_id, status, source, created_at, updated_at, last_status_change_at) "
                "VALUES (?, ?, ?, 'saved', 'assisted', ?, ?, ?)",
                (app_id, current_user.user_id, offer_id, now, now, now),
            )
            _record_status_change(conn, app_id, None, "saved", now)
            conn.commit()
            current_status = "saved"
        else:
            app_id = app_row["id"]
            current_status = app_row["status"]
    finally:
        conn.close()

    # 2. Resolve profile
    profile_dict = payload.profile
    if profile_dict is None:
        auth_profile = auth_db.get_profile(current_user.user_id)
        if auth_profile is not None:
            profile_dict = auth_profile.get("profile")
    if not profile_dict:
        raise HTTPException(
            status_code=400,
            detail={"message": "No profile available — upload a CV or provide profile in request body"},
        )

    # 3. Lazy imports (avoids circular imports at module load time)
    try:
        from documents.cv_generator import (  # type: ignore[import]
            _load_offer as _get_offer_dict,
            _profile_fingerprint as _compute_fingerprint,
            generate_cv,
        )
        from documents.cover_letter_generator import generate_cover_letter  # type: ignore[import]
        from documents.cache import (  # type: ignore[import]
            cache_set,
            make_cache_key,
            make_letter_cache_key,
        )
        from documents.schemas import (  # type: ignore[import]
            CvRequest,
            LETTER_TEMPLATE_VERSION,
            PROMPT_VERSION,
        )
    except ImportError as exc:
        logger.error("prepare: failed to import documents module: %s", exc)
        raise HTTPException(
            status_code=500,
            detail={"message": "CV generation module unavailable"},
        ) from exc

    # 4. Generate CV
    cv_req = CvRequest(offer_id=offer_id, profile=profile_dict)
    try:
        generate_cv(cv_req)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail={"message": f"Offer not found: {offer_id}"},
        ) from exc
    except Exception as exc:
        logger.error("prepare: generate_cv failed for offer %s: %s", offer_id, exc)
        warnings.append(f"CV generation error: {exc}")

    # 5. Compute profile fingerprint + CV cache key
    fingerprint = _compute_fingerprint(profile_dict)
    cv_cache_key = make_cache_key(fingerprint, offer_id, PROMPT_VERSION)

    # 6. Generate cover letter + cache it
    letter_cache_key: Optional[str] = None
    offer_dict = _get_offer_dict(offer_id)
    if offer_dict is not None:
        try:
            letter_payload, _letter_preview = generate_cover_letter(
                offer_id=offer_id,
                offer_title=offer_dict.get("title"),
                offer_company=offer_dict.get("company"),
                matched_skills=[],
                context_used=False,
            )
            letter_cache_key = make_letter_cache_key(fingerprint, offer_id, LETTER_TEMPLATE_VERSION)
            cache_set(
                key=letter_cache_key,
                doc_type="letter",
                offer_id=offer_id,
                profile_fingerprint=fingerprint,
                prompt_version=LETTER_TEMPLATE_VERSION,
                payload=letter_payload.model_dump(),
            )
        except Exception as exc:
            logger.warning("prepare: letter generation failed for offer %s: %s", offer_id, exc)
            warnings.append(f"Letter generation skipped: {exc}")
            letter_cache_key = None
    else:
        warnings.append("Offer not found for letter generation — letter skipped")

    # 7. Compute new application status
    new_status = "cv_ready" if current_status == "saved" else current_status
    status_changed = new_status != current_status

    # 8. Write apply_pack_runs row + update application (single connection, one commit)
    run_id = str(uuid.uuid4())
    payload_summary = json.dumps({
        "offer_id": offer_id,
        "prepared_at": now,
        "cv_cache_key": cv_cache_key,
        "letter_cache_key": letter_cache_key,
    })

    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO apply_pack_runs "
            "(id, application_id, user_id, offer_id, profile_fingerprint, "
            "cv_cache_key, letter_cache_key, template_id, template_version, "
            "payload_summary_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                app_id,
                current_user.user_id,
                offer_id,
                fingerprint,
                cv_cache_key,
                letter_cache_key,
                "cv_letter_v1",
                PROMPT_VERSION,
                payload_summary,
                now,
            ),
        )

        conn.execute(
            "UPDATE application_tracker SET "
            "current_cv_cache_key = ?, "
            "current_letter_cache_key = ?, "
            "status = ?, "
            "updated_at = ?"
            + (", last_status_change_at = ?" if status_changed else "")
            + " WHERE id = ?",
            [cv_cache_key, letter_cache_key, new_status, now]
            + ([now] if status_changed else [])
            + [app_id],
        )
        if status_changed:
            _record_status_change(conn, app_id, current_status, new_status, now)

        conn.commit()
    finally:
        conn.close()

    logger.info(
        "application_prepare offer_id=%s run_id=%s cv=%s letter=%s",
        offer_id,
        run_id,
        cv_cache_key,
        letter_cache_key or "none",
    )

    return PrepareResponse(
        ok=True,
        application_id=app_id,
        offer_id=offer_id,
        run_id=run_id,
        cv_cache_key=cv_cache_key,
        letter_cache_key=letter_cache_key,
        status=new_status,
        warnings=warnings,
    )
