import logging
from typing import Any, Dict, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit import AuditLog

logger = logging.getLogger(__name__)

class AuditService:
    """
    Service layer managing compliance and activity audit logging.
    """
    @staticmethod
    async def log_action(
        db: AsyncSession,
        user_id: Optional[UUID],
        action: str,
        resource: str,
        details: Optional[Dict[str, Any]] = None
    ) -> AuditLog:
        """
        Creates and stores an audit log record in PostgreSQL.
        """
        try:
            audit_log = AuditLog(
                user_id=user_id,
                action=action,
                resource=resource,
                details=details or {}
            )
            db.add(audit_log)
            # Flush so the primary key ID is assigned and returned, 
            # while leaving the commit to the main transaction block.
            await db.flush()
            
            logger.info(
                f"Audit logged | Action: {action} | User: {user_id} | Resource: {resource}"
            )
            return audit_log
        except Exception as e:
            logger.error(f"Failed to write audit log action {action} for user {user_id}: {e}")
            # Do not raise error to prevent secondary logging failure from breaking primary business flow
            pass

audit_service = AuditService()
