# Uploads

`POST /api/v1/uploads/` (multipart, escopo `uploads:write`), `GET /api/v1/uploads/<id>/download/`.

O que é checado, em ordem: a cota da organização (`QUOTA_UPLOAD_FILES_PER_ORG`,
`QUOTA_UPLOAD_BYTES_PER_ORG`), o tamanho (`UPLOAD_MAX_BYTES`, abaixo do limite do corpo da
requisição), a extensão em `UPLOAD_ALLOWED_EXTENSIONS`, cada segmento com ponto (assim `x.php.png`
falha), o conteúdo contra a extensão (magic bytes; texto deve ser UTF-8 sem NUL), arquivos office/zip
quanto a número de entradas, tamanho expandido, razão de compressão, caminhos inseguros e cifra. HTML,
SVG e tipos executáveis nunca são permitidos.

A chave de armazenamento nunca contém o nome do cliente; o content type servido é o detectado; os
downloads são anexos com `X-Content-Type-Options: nosniff` e uma CSP de sandbox.

Antivírus opcional: `UPLOAD_CLAMAV_ADDR=host:porta` (clamd). Quando definido, um scanner inacessível
recusa uploads, salvo `UPLOAD_CLAMAV_REQUIRED=false`. A conexão com o clamd é TCP simples: mantenha-a
numa rede privada.

## Armazenamento

Disco local por padrão. Para qualquer armazenamento compatível com S3 (AWS S3, MinIO, Cloudflare R2,
Backblaze B2) defina:

| Variável | Significado |
|---|---|
| `S3_BUCKET` | O bucket (a produção o exige, ou `OBJECT_STORAGE_REQUIRED=false` com volume persistente) |
| `S3_ENDPOINT_URL` | Para armazenamentos que não são AWS |
| `S3_REGION`, `S3_ADDRESSING_STYLE` | Como o armazenamento exigir |
| `AWS_MEDIA_KMS_KEY_ID` | Criptografia no servidor com KMS, opcional |

As credenciais vêm das variáveis padrão da AWS ou da identidade da plataforma (IAM role, workload
identity). Os nomes antigos `BUCKET_NAME`, `AWS_MEDIA_BUCKET`, `AWS_REGION` e `AWS_ENDPOINT_URL_S3`
continuam funcionando.

## Eliminação e retenção

Os arquivos são escopados ao tenant e auditados (`upload.created/downloaded/deleted`). Quando uma
linha é apagada por **qualquer** caminho (a API, uma eliminação de titular, a varredura de retenção)
um hook `post_delete` remove o arquivo armazenado, mas só se a mudança no banco for confirmada. A
retenção dos uploads segue a finalidade `product-content` (`retention_field` é `created_at`). Um
arquivo já removido do bucket à mão não é erro.

Backups do bucket são sua responsabilidade e expiram no seu cronograma; diga isso no aviso de
privacidade.
