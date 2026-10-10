from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.aws.s3_storage import CONTENT_TYPES, build_key, get_storage
from app.config import get_settings
from app.database import get_db
from app.models.document import DocStatus, Document
from app.models.user import User
from app.rag.pipeline import ingest_document
from app.routers.subjects import get_owned_subject
from app.schemas.document import DocumentOut, DownloadOut
from app.security.audit import audit
from app.security.file_validator import validate_upload
from app.security.rate_limiter import limiter
from app.security.rbac import require_student

router = APIRouter(prefix="/api/documents", tags=["documents"])
settings = get_settings()


def get_owned_document(db: Session, doc_id: str, user: User) -> Document:
    doc = db.query(Document).filter(Document.id == doc_id, Document.owner_id == user.id).first()
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return doc


@router.get("", response_model=list[DocumentOut])
def list_documents(subject_id: str, user: User = Depends(require_student), db: Session = Depends(get_db)):
    get_owned_subject(db, subject_id, user)
    return (
        db.query(Document)
        .filter(Document.subject_id == subject_id, Document.owner_id == user.id)
        .order_by(Document.created_at.desc())
        .all()
    )


@router.post("", response_model=DocumentOut, status_code=201)
@limiter.limit(settings.RATE_LIMIT_UPLOAD)
async def upload_document(
    request: Request,
    background: BackgroundTasks,
    subject_id: str = Form(..., max_length=36),
    file: UploadFile = File(...),
    user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    subject = get_owned_subject(db, subject_id, user)

    # Per-user quotas (cost and abuse control)
    count, used = (
        db.query(func.count(Document.id), func.coalesce(func.sum(Document.size_bytes), 0))
        .filter(Document.owner_id == user.id)
        .one()
    )
    if count >= settings.MAX_DOCS_PER_USER:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Document limit reached ({settings.MAX_DOCS_PER_USER})")

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    data = await file.read(max_bytes + 1)  # never read more than the limit into memory
    checked = validate_upload(file.filename or "", data)

    if used + len(data) > settings.MAX_STORAGE_MB_PER_USER * 1024 * 1024:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Storage quota exceeded")

    key = build_key(user.id, subject.id, checked.file_type)  # random UUID name, never the user's filename
    get_storage().put(key, data, checked.file_type)

    doc = Document(
        owner_id=user.id,
        subject_id=subject.id,
        filename=checked.safe_name,
        s3_key=key,
        file_type=checked.file_type,
        size_bytes=len(data),
        status=DocStatus.processing,
    )
    db.add(doc)
    db.commit()
    audit(db, "upload", user_id=user.id, resource=doc.id, request=request,
          details={"filename": doc.filename, "bytes": len(data)})
    background.add_task(ingest_document, doc.id)
    return doc


@router.get("/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: str, user: User = Depends(require_student), db: Session = Depends(get_db)):
    return get_owned_document(db, doc_id, user)


@router.post("/{doc_id}/reprocess", response_model=DocumentOut)
def reprocess_document(
    doc_id: str, background: BackgroundTasks, user: User = Depends(require_student), db: Session = Depends(get_db)
):
    doc = get_owned_document(db, doc_id, user)
    if doc.status == DocStatus.processing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Document is already being processed")
    doc.status, doc.error = DocStatus.processing, None
    db.commit()
    background.add_task(ingest_document, doc.id)
    return doc


@router.get("/{doc_id}/download")
def download_document(
    doc_id: str, request: Request, user: User = Depends(require_student), db: Session = Depends(get_db)
):
    doc = get_owned_document(db, doc_id, user)
    storage = get_storage()
    audit(db, "download", user_id=user.id, resource=doc.id, request=request)
    url = storage.presigned_url(doc.s3_key, doc.filename)
    if url:  # S3: short-lived presigned link (5 minutes)
        return DownloadOut(url=url, expires_in=settings.PRESIGNED_URL_SECONDS)
    return Response(
        content=storage.get(doc.s3_key),
        media_type=CONTENT_TYPES[doc.file_type],
        headers={"Content-Disposition": f'attachment; filename="{doc.filename}"'},
    )


@router.delete("/{doc_id}", status_code=204)
def delete_document(
    doc_id: str, request: Request, user: User = Depends(require_student), db: Session = Depends(get_db)
):
    doc = get_owned_document(db, doc_id, user)
    get_storage().delete(doc.s3_key)
    db.delete(doc)  # chunks are removed by ON DELETE CASCADE
    db.commit()
    audit(db, "delete_document", user_id=user.id, resource=doc_id, request=request)
