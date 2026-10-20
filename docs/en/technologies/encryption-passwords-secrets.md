# Encryption, passwords, and secrets

[Versão em português](../../pt-BR/tecnologias/criptografia-senhas-segredos.md) ·
[Back to the learning path](../learning-path.md)

## Password hashing: Argon2

Passwords should not be decryptable. Argon2 creates a slow, salted hash:

```text
provided password → Argon2 → compare with stored hash
```

After a database leak, every password guess remains expensive. The project requires at least 12
characters, but important accounts still need MFA and login lockout.

## Field encryption: AES-256-GCM

Especially sensitive fields use a key because their content must be recoverable. AES-GCM provides:

- **confidentiality:** the value is unreadable without the key;
- **integrity:** ciphertext modification is detected;
- **random nonce:** equal values produce different ciphertext;
- **AAD:** binds ciphertext to its model and column.

It cannot stop swaps between rows in the same column or an incorrectly authorized view. It also
makes normal search, indexes, and uniqueness difficult.

## HMAC and blind indexes

HMAC supports equality comparison without storing the original value. A secret key prevents
someone with only the database from cheaply generating all results. Use separate namespaces per
purpose. Partial search is unavailable.

## Separate secrets

The Django signing key, field encryption key ring, privacy HMAC key, and credentials for database,
Redis, email, Sentry, and storage have different jobs.

Never reuse keys between products or environments. Do not commit secrets or put them in Docker
layers, logs, Sentry, or `.env.example`.

## Rotation

Add a new field key, make it active, deploy, rewrite records in batches, verify backups, and only
then remove the old key. Losing all keys loses the data; leaking keys with the database sharply
reduces protection.

Encrypt when direct database disclosure has high impact and normal search is unnecessary. First
minimize collection: data that does not exist cannot leak.
