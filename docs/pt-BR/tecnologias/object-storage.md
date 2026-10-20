# Object storage: Tigris e S3

[English version](../../en/technologies/object-storage.md) ·
[Voltar à trilha](../trilha-aprendizado.md)

## O que é?

Object storage guarda arquivos como objetos dentro de buckets. S3 é o protocolo mais comum;
Tigris oferece uma API compatível. `django-storages` conecta o sistema de arquivos do Django ao
bucket.

## Por que não salvar na Machine?

O filesystem de uma Machine Fly é efêmero: uma nova Machine não recebe automaticamente os
arquivos da anterior. Várias instâncias também precisam enxergar o mesmo conteúdo.

Use object storage para:

- uploads de usuários;
- imagens e documentos;
- relatórios;
- exportações de dados.

WhiteNoise serve somente arquivos estáticos públicos da aplicação, como CSS do Admin.

## Bucket privado e URL assinada

O bucket deve ser privado. Uma URL assinada libera um objeto específico por pouco tempo:

```text
usuário autenticado → API verifica permissão → gera URL com expiração → download
```

Não torne o bucket público para facilitar desenvolvimento.

## Segurança

- valide tamanho e tipo real do arquivo;
- gere nomes imprevisíveis;
- verifique tenant e permission em upload/download;
- não use o nome enviado pelo usuário como caminho confiável;
- configure criptografia no provedor;
- registre acesso relevante sem copiar o conteúdo;
- defina retenção e exclusão também para backups.

Antivírus ou sandbox pode ser necessário para documentos enviados por terceiros.

## LGPD e operação

Confirme região, suboperadores e transferências internacionais do provedor. Uma URL expirada não
apaga o objeto. Exclusão, versionamento, lifecycle e backups precisam refletir a política do
produto.

Monitore espaço, erros, latência e custo de saída. Teste restauração e acesso após rotação de
credenciais.
