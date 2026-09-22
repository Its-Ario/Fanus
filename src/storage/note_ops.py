from __future__ import annotations

from src.storage.audit import record_audit
from src.storage.db import get_database_manager
from src.storage.models import AuditLog, CounselorNote, User


class NotePermissionError(PermissionError):
    pass


class NoteValidationError(ValueError):
    pass


def _actor(actor):
    try:
        fresh = User.get_by_id(actor.id)
    except (AttributeError, User.DoesNotExist) as exc:
        raise NotePermissionError("دسترسی لازم برای یادداشت های محرمانه را ندارید.") from exc
    if not fresh.is_active or fresh.role != "counselor":
        raise NotePermissionError("دسترسی لازم برای یادداشت های محرمانه را ندارید.")
    return fresh


def _require_unlocked():
    manager = get_database_manager()
    if not manager.vault_unlocked:
        raise NotePermissionError("ابتدا گاوصندوق محرمانه را باز کنید.")
    return manager


def _payload(title: str, tags: str, content: str) -> tuple[str, str, str]:
    content = (content or "").strip()
    if not content:
        raise NoteValidationError("متن یادداشت را وارد کنید.")
    return (
        (title or "").strip() or "یادداشت مشاوره",
        (tags or "").strip() or "عمومی",
        content,
    )


def _record_note_audit(actor, action: str, note: CounselorNote) -> None:
    event = record_audit(actor, action, "CounselorNote", note.id)
    event.student_id = note.student_id
    event.save()


def create_note(actor, student, *, title: str, tags: str, content: str) -> CounselorNote:
    actor = _actor(actor)
    manager = _require_unlocked()
    title, tags, content = _payload(title, tags, content)
    with manager.transaction(vault=True):
        note = CounselorNote.create(
            student_id=student.id, author_id=actor.id, title=title, tags=tags, content=content
        )
    _record_note_audit(actor, "note.create", note)
    return note


def list_notes(actor, student) -> list[CounselorNote]:
    actor = _actor(actor)
    _require_unlocked()
    notes = list(
        CounselorNote.select()
        .where((CounselorNote.student_id == student.id) & (CounselorNote.author_id == actor.id))
        .order_by(CounselorNote.created_at.desc())
    )
    for note in notes:
        _record_note_audit(actor, "note.view", note)
    return notes


def update_note(actor, note_id, *, title: str, tags: str, content: str) -> CounselorNote:
    actor = _actor(actor)
    manager = _require_unlocked()
    title, tags, content = _payload(title, tags, content)
    try:
        note = CounselorNote.get(
            (CounselorNote.id == note_id) & (CounselorNote.author_id == actor.id)
        )
    except CounselorNote.DoesNotExist as exc:
        raise NotePermissionError("این یادداشت متعلق به شما نیست.") from exc
    with manager.transaction(vault=True):
        note.title = title
        note.tags = tags
        note.content = content
        note.save()
    _record_note_audit(actor, "note.edit", note)
    return note


def list_note_audit(actor, student) -> list[AuditLog]:
    actor = _actor(actor)
    return list(
        AuditLog.select()
        .where(
            (AuditLog.actor_id == actor.id)
            & (AuditLog.student_id == student.id)
            & AuditLog.action.startswith("note.")
        )
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    )
