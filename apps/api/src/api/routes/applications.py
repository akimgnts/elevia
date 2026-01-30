"""
applications.py - Applications Tracker routes (Candidatures V0)
"""

import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from ..schemas.applications import (
    ApplicationCreate,
    ApplicationItem,
    ApplicationListResponse,
    ApplicationStatus,
    ApplicationUpdate,
)
from ..utils.db import get_connection

router = APIRouter(tags=["applications"])

STATUS_VALUES = {s.value for s in ApplicationStatus}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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
        raise HTTPException(status_code=400, detail={"message": "Invalid next_follow_up_date (YYYY-MM-DD)"})
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail={"message": "Invalid next_follow_up_date (YYYY-MM-DD)"})
    return value


@router.get("/applications", response_model=ApplicationListResponse)
async def list_applications() -> ApplicationListResponse:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, offer_id, status, note, next_follow_up_date, created_at, updated_at "
            "FROM application_tracker ORDER BY updated_at DESC"
        ).fetchall()
    finally:
        conn.close()

    items = [
        ApplicationItem(
            id=row[0],
            offer_id=row[1],
            status=row[2],
            note=row[3],
            next_follow_up_date=row[4],
            created_at=row[5],
            updated_at=row[6],
        )
        for row in rows
    ]
    return ApplicationListResponse(items=items)


@router.get("/applications/{offer_id}", response_model=ApplicationItem)
async def get_application(offer_id: str) -> ApplicationItem:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, offer_id, status, note, next_follow_up_date, created_at, updated_at "
            "FROM application_tracker WHERE offer_id = ?",
            (offer_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail={"message": "Application not found"})

    return ApplicationItem(
        id=row[0],
        offer_id=row[1],
        status=row[2],
        note=row[3],
        next_follow_up_date=row[4],
        created_at=row[5],
        updated_at=row[6],
    )


@router.post("/applications", response_model=ApplicationItem)
async def upsert_application(payload: ApplicationCreate) -> JSONResponse:
    status = _validate_status(payload.status)
    note = payload.note
    next_follow_up_date = _validate_date(payload.next_follow_up_date)

    now = _utc_now()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, created_at FROM application_tracker WHERE offer_id = ?",
            (payload.offer_id,),
        ).fetchone()

        if row is None:
            app_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO application_tracker (id, offer_id, status, note, next_follow_up_date, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (app_id, payload.offer_id, status, note, next_follow_up_date, now, now),
            )
            conn.commit()
            created = True
        else:
            app_id = row[0]
            conn.execute(
                "UPDATE application_tracker SET status = ?, note = ?, next_follow_up_date = ?, updated_at = ? "
                "WHERE offer_id = ?",
                (status, note, next_follow_up_date, now, payload.offer_id),
            )
            conn.commit()
            created = False

        item = conn.execute(
            "SELECT id, offer_id, status, note, next_follow_up_date, created_at, updated_at "
            "FROM application_tracker WHERE offer_id = ?",
            (payload.offer_id,),
        ).fetchone()
    finally:
        conn.close()

    if item is None:
        raise HTTPException(status_code=500, detail={"message": "Failed to upsert application"})

    result = ApplicationItem(
        id=item[0],
        offer_id=item[1],
        status=item[2],
        note=item[3],
        next_follow_up_date=item[4],
        created_at=item[5],
        updated_at=item[6],
    )
    status_code = 201 if created else 200
    return JSONResponse(status_code=status_code, content=result.model_dump())


@router.patch("/applications/{offer_id}", response_model=ApplicationItem)
async def patch_application(offer_id: str, payload: ApplicationUpdate) -> ApplicationItem:
    if payload.status is None and payload.note is None and payload.next_follow_up_date is None:
        raise HTTPException(status_code=400, detail={"message": "No fields to update"})

    status = _validate_status(payload.status) if payload.status is not None else None
    next_follow_up_date = _validate_date(payload.next_follow_up_date)
    now = _utc_now()

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM application_tracker WHERE offer_id = ?",
            (offer_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail={"message": "Application not found"})

        conn.execute(
            "UPDATE application_tracker SET "
            "status = COALESCE(?, status), "
            "note = COALESCE(?, note), "
            "next_follow_up_date = COALESCE(?, next_follow_up_date), "
            "updated_at = ? "
            "WHERE offer_id = ?",
            (status, payload.note, next_follow_up_date, now, offer_id),
        )
        conn.commit()

        item = conn.execute(
            "SELECT id, offer_id, status, note, next_follow_up_date, created_at, updated_at "
            "FROM application_tracker WHERE offer_id = ?",
            (offer_id,),
        ).fetchone()
    finally:
        conn.close()

    if item is None:
        raise HTTPException(status_code=404, detail={"message": "Application not found"})

    return ApplicationItem(
        id=item[0],
        offer_id=item[1],
        status=item[2],
        note=item[3],
        next_follow_up_date=item[4],
        created_at=item[5],
        updated_at=item[6],
    )


@router.delete("/applications/{offer_id}", status_code=204)
async def delete_application(offer_id: str) -> None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM application_tracker WHERE offer_id = ?",
            (offer_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail={"message": "Application not found"})
        conn.execute("DELETE FROM application_tracker WHERE offer_id = ?", (offer_id,))
        conn.commit()
    finally:
        conn.close()
    return None
