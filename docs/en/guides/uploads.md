# Uploads

`POST /api/v1/uploads/` (multipart, scope `uploads:write`), `GET /api/v1/uploads/<id>/download/`.

What is checked, in order: the organization's quota (`QUOTA_UPLOAD_FILES_PER_ORG`,
`QUOTA_UPLOAD_BYTES_PER_ORG`), size (`UPLOAD_MAX_BYTES`, below the request body cap), extension in
`UPLOAD_ALLOWED_EXTENSIONS`, every dotted segment (so `x.php.png` fails), the content against the
extension (magic bytes; text must be UTF-8 without NUL), office/zip files for entry count, expanded
size, compression ratio, unsafe paths and encryption. HTML, SVG and executable types are never
allowed.

The storage key never contains the client's name; the served content type is the sniffed one;
downloads are attachments with `X-Content-Type-Options: nosniff` and a sandbox CSP.

Optional antivirus: `UPLOAD_CLAMAV_ADDR=host:port` (clamd). When set, an unreachable scanner
refuses uploads unless `UPLOAD_CLAMAV_REQUIRED=false`. The connection to clamd is plain TCP: keep
it on a private network.

## Storage

Local disk by default. For any S3-compatible store (AWS S3, MinIO, Cloudflare R2, Backblaze B2) set:

| Variable | Meaning |
|---|---|
| `S3_BUCKET` | The bucket (production requires it, or `OBJECT_STORAGE_REQUIRED=false` with a persistent volume) |
| `S3_ENDPOINT_URL` | For non-AWS stores |
| `S3_REGION`, `S3_ADDRESSING_STYLE` | As the store requires |
| `AWS_MEDIA_KMS_KEY_ID` | Server-side encryption with KMS, optional |

Credentials come from the standard AWS variables or the platform identity (IAM role, workload
identity). The older names `BUCKET_NAME`, `AWS_MEDIA_BUCKET`, `AWS_REGION` and
`AWS_ENDPOINT_URL_S3` still work.

## Erasure and retention

Files are tenant-scoped and audited (`upload.created/downloaded/deleted`). When a row is deleted by
**any** path (the API, a data-subject erasure, the retention sweep) a `post_delete` hook removes the
stored file, but only if the database change commits. Retention for uploads follows the
`product-content` purpose (`retention_field` is `created_at`). A file already removed from the
bucket by hand is not an error.

Backups of the bucket are your responsibility and expire on your schedule; say so in the privacy
notice.
