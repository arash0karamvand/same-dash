"""Validated attachment storage with explicit, database-enforced source links."""

from pathlib import Path

from backend.models import (
    DocumentAttachment,
    GoodsReceipt,
    InventoryConsumption,
    InventoryReservation,
    InventoryTransaction,
    JournalEntry,
    ProductionOrder,
    PurchaseInvoice,
    Sale,
)

MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024
ALLOWED_TYPES = {
    ".pdf": {"application/pdf"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".webp": {"image/webp"},
    ".doc": {"application/msword", "application/octet-stream"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ".xls": {"application/vnd.ms-excel", "application/octet-stream"},
    ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
}

SOURCE_MODELS = {
    "journal": (JournalEntry, "journal"),
    "sale": (Sale, "sale"),
    "production_order": (ProductionOrder, "production_order"),
    "purchase_invoice": (PurchaseInvoice, "purchase_invoice"),
    "inventory_transaction": (InventoryTransaction, "inventory_transaction"),
    "reservation": (InventoryReservation, "reservation"),
    "consumption": (InventoryConsumption, "consumption"),
    "goods_receipt": (GoodsReceipt, "goods_receipt"),
}


def resolve_source(source_type, source_id):
    try:
        model, field = SOURCE_MODELS[source_type]
    except KeyError as exc:
        raise ValueError("Unsupported attachment source type.") from exc
    try:
        source = model.objects.get(pk=source_id)
    except model.DoesNotExist as exc:
        raise ValueError("Attachment source was not found.") from exc
    return field, source


def _signature_is_valid(extension, header):
    if extension == ".pdf":
        return header.startswith(b"%PDF-")
    if extension == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if extension in {".jpg", ".jpeg"}:
        return header.startswith(b"\xff\xd8\xff")
    if extension == ".webp":
        return header.startswith(b"RIFF") and header[8:12] == b"WEBP"
    if extension in {".doc", ".xls"}:
        return header.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    if extension in {".docx", ".xlsx"}:
        return header.startswith(b"PK\x03\x04")
    return False


def validate_upload(upload):
    name = Path(upload.name or "").name
    extension = Path(name).suffix.lower()
    content_type = (getattr(upload, "content_type", "") or "").lower()
    if not name or extension not in ALLOWED_TYPES:
        raise ValueError("Only PDF, image, Word, and Excel documents are supported.")
    if content_type not in ALLOWED_TYPES[extension]:
        raise ValueError("The uploaded file type does not match its extension.")
    if upload.size <= 0 or upload.size > MAX_ATTACHMENT_SIZE:
        raise ValueError("Attachment size must be between 1 byte and 10 MB.")
    header = upload.read(16)
    upload.seek(0)
    if not _signature_is_valid(extension, header):
        raise ValueError("The uploaded file signature is invalid.")
    return name, content_type


def create_attachment(upload, *, source_type, source_id, user=None, description=""):
    name, content_type = validate_upload(upload)
    field, source = resolve_source(source_type, source_id)
    return DocumentAttachment.objects.create(
        file=upload,
        original_name=name,
        content_type=content_type,
        size=upload.size,
        description=(description or "").strip()[:300],
        uploaded_by=user,
        **{field: source},
    )


def attachment_to_dict(attachment):
    source_type = next(
        key
        for key, (_model, field) in SOURCE_MODELS.items()
        if getattr(attachment, f"{field}_id") is not None
    )
    field = SOURCE_MODELS[source_type][1]
    return {
        "id": attachment.id,
        "uuid": str(attachment.uuid),
        "original_name": attachment.original_name,
        "content_type": attachment.content_type,
        "size": attachment.size,
        "description": attachment.description,
        "source_type": source_type,
        "source_id": getattr(attachment, f"{field}_id"),
        "url": attachment.file.url,
        "uploaded_by": attachment.uploaded_by_id,
        "created_at": attachment.created_at.isoformat(),
    }
