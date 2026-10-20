# Object storage: Tigris and S3

[Versão em português](../../pt-BR/tecnologias/object-storage.md) ·
[Back to the learning path](../learning-path.md)

## What is it?

Object storage keeps files as objects inside buckets. S3 is the common protocol; Tigris provides a
compatible API. `django-storages` connects Django's file interface to the bucket.

## Why not save files on a Machine?

A Fly Machine filesystem is ephemeral, and other instances do not automatically share its files.

Use object storage for user uploads, images, documents, reports, and data exports. WhiteNoise only
serves public application assets such as Admin CSS.

## Private buckets and signed URLs

The bucket must be private. A signed URL grants short-lived access to one object:

```text
authenticated user → API checks permission → expiring URL → download
```

Never make a bucket public merely to simplify development.

## Security

- validate actual type and size;
- use unpredictable names;
- check tenant and permission on upload/download;
- never trust the user-provided filename as a path;
- configure provider encryption;
- define retention and backup deletion;
- consider antivirus or sandboxing for untrusted documents.

## LGPD and operations

Confirm provider region, subprocessors, and international transfers. An expired URL does not
delete an object. Deletion, versioning, lifecycle rules, and backups must match product policy.

Monitor capacity, errors, latency, and egress cost. Test restoration and access after credential
rotation.
