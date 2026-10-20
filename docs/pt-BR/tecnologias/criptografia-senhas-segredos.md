# Criptografia, senhas e segredos

[English version](../../en/technologies/encryption-passwords-secrets.md) ·
[Voltar à trilha](../trilha-aprendizado.md)

## Hash de senha: Argon2

Senha não deve ser decriptada. Argon2 cria um hash lento e com salt:

```text
senha informada → Argon2 → comparação com hash salvo
```

Se o banco vazar, cada tentativa de adivinhar uma senha continua cara. O projeto exige mínimo de
12 caracteres, mas MFA e bloqueio de login ainda são necessários para contas importantes.

## Criptografia de campo: AES-256-GCM

Campos especialmente sensíveis usam uma chave para poderem ser recuperados. AES-GCM oferece:

- **confidencialidade:** sem chave, o conteúdo não é legível;
- **integridade:** alteração do ciphertext é detectada;
- **nonce aleatório:** valores iguais geram ciphertexts diferentes;
- **AAD:** vincula o ciphertext ao model e à coluna.

Ele não impede troca entre linhas da mesma coluna e não protege contra uma view autorizando acesso
indevido. Também dificulta busca, índice e unicidade.

## HMAC e blind index

HMAC permite comparar igualdade sem salvar o valor original. A chave secreta impede que alguém
com apenas o banco calcule facilmente todos os resultados. Use namespaces diferentes por
finalidade. Busca parcial não funciona.

## Segredos diferentes

- `DJANGO_SECRET_KEY`: assinatura do Django;
- `FIELD_ENCRYPTION_KEYS`: criptografia dos campos;
- `PRIVACY_HMAC_KEY`: comparações protegidas;
- credenciais de banco, Redis, e-mail, Sentry e storage.

Nunca reutilize chaves entre produtos ou ambientes. Não coloque segredos no Git, imagem Docker,
logs, Sentry ou `.env.example`.

## Rotação

Para campos cifrados: adicione a nova chave, torne-a ativa, publique, regrave registros em lotes,
verifique backups e só então remova a antiga. Perder todas as chaves significa perder os dados;
vazar a chave junto do banco reduz muito a proteção.

## Quando criptografar?

Criptografe quando a leitura direta do banco teria alto impacto e o campo não precisar de busca
normal. Minimize a coleta antes de adicionar criptografia: o dado que não existe não pode vazar.

Criptografia é um controle técnico, não uma prova automática de conformidade LGPD.
