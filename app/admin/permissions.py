"""
app/admin/permissions.py

Role gate for admin endpoints. Super admins always pass.
"""

from fastapi import Depends, HTTPException, status

from app.admin import models as admin_models
from app.admin.routers import get_current_admin_user

R = admin_models.AdminRoleEnum

# Edit these two tuples to change who may do what.
VERIFICATION_ROLES = (R.SUPER_ADMIN, R.VERIFICATION_OFFICER)
SUSPENSION_ROLES = (R.SUPER_ADMIN, R.DISPUTE_MANAGER)


def require_roles(*allowed):
    def dependency(
        admin: admin_models.AdminUser = Depends(get_current_admin_user),
    ) -> admin_models.AdminUser:
        if admin.is_superadmin or admin.role in allowed:
            return admin
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your admin role is not permitted to perform this action.",
        )

    return dependency
