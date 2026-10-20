# Uploads

`POST /api/v1/uploads/` (multipart, scope `uploads:write`), `GET /api/v1/uploads/<id>/download/`.

What is checked, in order: size (`UPLOAD_MAX_BYTES`, below the request body cap), extension in
`UPLOAD_ALLOWED_EXTENSIONS`, every dotted segment (so `x.php.png` fails), the content against the
extension (magic bytes; text must be UTF-8 without NUL), office/zip files for entry count, expanded
size, compression ratio, unsafe paths and encryption. HTML, SVG and executable types are never
allowed.

The storage key never contains the client's name; the served content type is the sniffed one;
downloads are attachments with `X-Content-Type-Options: nosniff` and a sandbox CSP.

Optional antivirus: `UPLOAD_CLAMAV_ADDR=host:port` (clamd). When set, an unreachable scanner
refuses uploads unless `UPLOAD_CLAMAV_REQUIRED=false`.

Storage is local disk by default; set `S3_BUCKET` (and `S3_ENDPOINT_URL` for MinIO/R2/B2) for any
S3-compatible store. Files are tenant-scoped, audited (`upload.created/downloaded/deleted`) and
erased with their uploader's data (LGPD catalog).
