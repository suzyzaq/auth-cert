const allowedMimeTypes = new Set([
  "application/pdf",
  "image/jpeg",
  "image/png",
  "image/webp",
]);

export interface AttachmentMetadata {
  mime: string;
  size: number;
}

export function validateAttachment(
  metadata: AttachmentMetadata,
  maxBytes = 25 * 1024 * 1024,
): AttachmentMetadata {
  if (!allowedMimeTypes.has(metadata.mime)) {
    throw new Error(`unsupported attachment type: ${metadata.mime}`);
  }
  if (!Number.isSafeInteger(metadata.size) || metadata.size <= 0) {
    throw new Error("invalid attachment size");
  }
  if (metadata.size > maxBytes) {
    throw new Error(`attachment exceeds ${maxBytes} bytes`);
  }
  return metadata;
}
