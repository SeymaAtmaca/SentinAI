
@router.get("/me")
async def get_current_user(ctx: dict = Depends(get_current_tenant_context)):
    return {"user_id": ctx["user_id"], "tenant_slug": ctx["tenant_slug"]}