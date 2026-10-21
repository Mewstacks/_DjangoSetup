# E-mail e idiomas

## Enviando e-mail

O e-mail passa pelo `MAILERS["default"]` do Django. Em desenvolvimento imprime no console. Em
produção o backend SMTP é o padrão e os validadores recusam `console`, `locmem` e `dummy`:

| Variável | Significado |
|---|---|
| `EMAIL_BACKEND` | Caminho pontilhado do backend (padrão: SMTP) |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS` | O servidor SMTP (porta 587 com STARTTLS por padrão) |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Credenciais, do seu cofre de segredos |
| `DEFAULT_FROM_EMAIL`, `SERVER_EMAIL` | Remetente do e-mail de usuários e de erros |

`python manage.py doctor` avisa quando nada é de fato entregue. Um envio que falha nunca derruba a
requisição que o provocou (`apps.common.mail.send_safely` registra), então uma queda do provedor de
e-mail degrada códigos de cadastro e avisos de privacidade, não a API; acompanhe os logs.

## Quem envia o quê

- **Cadastro, verificação e redefinição de senha** (allauth): códigos de uso único. Os templates
  ficam em `src/templates/allauth/`; para trocar uma mensagem, adicione o mesmo caminho no seu
  diretório de templates.
- **LGPD** (`apps.privacy`): confirmação de solicitação, link de exportação, conclusão, recusa,
  lembretes ao DPO. Os textos estão em `src/apps/privacy/messages.py`.

## Idiomas

`LANGUAGE_CODE` é `pt-br` e o fuso `America/Sao_Paulo`. O que um titular lê é escolhido por
`PRIVACY_MAIL_LANGUAGE` (`pt-br` por padrão, `en` disponível; um valor desconhecido cai para inglês).
Para adicionar um idioma, inclua um dicionário em `CATALOG` no `messages.py`; um teste falha quando
um idioma não tem uma chave ou usa marcadores diferentes.

O resto da plataforma responde em termos de máquina (`code` de erro, `detail` em inglês), porque seus
clientes são programas. O texto para usuários finais do **seu** produto pertence ao seu frontend. Se
você renderiza HTML no Django, use `gettext`, adicione
`django.middleware.locale.LocaleMiddleware` depois do middleware de sessão e mantenha os catálogos
na pasta `locale/` do seu app.

Os links nos e-mails são absolutos quando `PUBLIC_URL` está definido (obrigatório em produção): um
caminho relativo num cliente de e-mail não leva a lugar nenhum.
