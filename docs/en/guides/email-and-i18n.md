# E-mail and languages

## Sending mail

Mail goes through Django's `MAILERS["default"]`. Development prints to the console. In production
the SMTP backend is the default and the validators refuse `console`, `locmem` and `dummy`:

| Variable | Meaning |
|---|---|
| `EMAIL_BACKEND` | Dotted path of the backend (default: SMTP) |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS` | The SMTP server (port 587 with STARTTLS by default) |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Credentials, from your secret store |
| `DEFAULT_FROM_EMAIL`, `SERVER_EMAIL` | Sender of user mail and of errors |

`python manage.py doctor` warns when nothing is actually delivered. A failing send never fails the
request that triggered it (`apps.common.mail.send_safely` logs it), so an outage of the mail
provider degrades sign-up codes and privacy notices, not the API; watch the logs.

## Who sends what

- **Sign-up, verification and password reset** (allauth): one-time codes. Templates live in
  `src/templates/allauth/`; override a message by adding the same path in your own template
  directory.
- **LGPD** (`apps.privacy`): request confirmation, export link, completion, denial, reminders to the
  DPO. The texts are in `src/apps/privacy/messages.py`.

## Languages

`LANGUAGE_CODE` is `pt-br` and the time zone `America/Sao_Paulo`. What a data subject reads is
chosen by `PRIVACY_MAIL_LANGUAGE` (`pt-br` by default, `en` available; an unknown value falls back
to English). To add a language, add a dictionary to `CATALOG` in `messages.py`; a test fails when a
language lacks a key or uses different placeholders.

The rest of the platform answers in machine terms (error `code`s, English `detail`), because its
clients are programs. Text meant for end users of **your** product belongs in your own front end.
If you render HTML in Django, use `gettext`, add `django.middleware.locale.LocaleMiddleware` after
the session middleware and keep the catalogs in your app's `locale/` folder.

Links in mail are absolute when `PUBLIC_URL` is set (required in production): a relative path in a
mail client goes nowhere.
