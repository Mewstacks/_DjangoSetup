# Uploads

`POST /api/v1/uploads/` (multipart, escopo `uploads:write`), `GET /api/v1/uploads/<id>/download/`.

O que é checado, em ordem: tamanho (`UPLOAD_MAX_BYTES`, abaixo do teto do corpo da requisição),
extensão em `UPLOAD_ALLOWED_EXTENSIONS`, cada segmento com ponto (então `x.php.png` falha), o
conteúdo contra a extensão (magic bytes; texto deve ser UTF-8 sem NUL), arquivos office/zip por
número de entradas, tamanho expandido, razão de compressão, caminhos inseguros e criptografia.
HTML, SVG e tipos executáveis nunca são permitidos.

A chave de armazenamento nunca contém o nome do cliente; o content type servido é o detectado;
downloads são attachments com `X-Content-Type-Options: nosniff` e CSP sandbox.

Antivírus opcional: `UPLOAD_CLAMAV_ADDR=host:porta` (clamd). Quando definido, um scanner
inalcançável recusa uploads, salvo `UPLOAD_CLAMAV_REQUIRED=false`.

O armazenamento é disco local por padrão; defina `S3_BUCKET` (e `S3_ENDPOINT_URL` para
MinIO/R2/B2) para qualquer store compatível com S3. Arquivos são por tenant, auditados
(`upload.created/downloaded/deleted`) e apagados com os dados de quem enviou (catálogo LGPD).
