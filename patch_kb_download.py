import re

path = "backend/app/api/v1/endpoints/knowledge_base.py"
with open(path, "r") as f:
    orig = f.read()

# Add download endpoint right before delete_document
download_code = """
@router.get("/documents/{doc_id}/download")
async def download_document(
    doc_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    \"\"\"Download the text content of a document.\"\"\"
    from sqlalchemy import select
    from fastapi.responses import PlainTextResponse
    from app.models.knowledge_base import Document as DocumentModel

    doc_result = await db.execute(
        select(DocumentModel).where(DocumentModel.id == doc_id)
    )
    doc = doc_result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Verify kb ownership
    kb_result = await db.execute(
        select(KnowledgeBaseModel).where(
            KnowledgeBaseModel.id == doc.knowledge_base_id,
            KnowledgeBaseModel.organization_id == org_id
        )
    )
    kb = kb_result.scalar_one_or_none()

    if not kb:
        raise HTTPException(status_code=403, detail="Access denied")
        
    filename = doc.title
    if not filename.lower().endswith(".txt"):
        filename += ".txt"
        
    headers = {
        'Content-Disposition': f'attachment; filename="{filename}"'
    }

    return PlainTextResponse(content=doc.content, headers=headers)

@router.delete("/documents/{doc_id}", status_code=204)
"""

res = orig.replace('@router.delete("/documents/{doc_id}", status_code=204)', download_code.strip())

with open(path, "w") as f:
    f.write(res)

