from src.storage.models import AuditLog


def record_audit(actor, action, entity, target_id=None, details=None):
    """Record an audit event"""
    return AuditLog.create(
        actor_id=getattr(actor, "id", None),
        actor_name=actor.full_name,
        action=action,
        target_entity=entity,
        target_id=target_id,
        details=details,
    )
