# Política de Privacidade — {{Nome do produto}}

> **Modelo, não aconselhamento jurídico.** Adapte ao seu tratamento real e peça revisão de um
> advogado com experiência em LGPD antes de publicar. Apague esta nota e os itens que não se
> aplicam. Versão {{versão}}, em vigor desde {{data}}.

## 1. Quem é o responsável

**Controlador:** {{Razão social}}, CNPJ {{CNPJ}}, {{endereço}}.
**Encarregado (DPO):** {{nome}}, {{e-mail}} / {{URL de contato}}.

Quando tratamos dados de membros de uma organização cliente, atuamos como **operador** e a
organização é a controladora; neste caso, as solicitações devem ser feitas a ela. {{Ajuste conforme o contrato.}}

## 2. Quais dados tratamos, para quê e com que base legal

| Finalidade | Dados | Base legal (LGPD art. 7) | Por quanto tempo |
|---|---|---|---|
| Criar e proteger a conta | e-mail, nome, credenciais, sessões, chaves | execução de contrato | enquanto a conta existir + {{prazo}} |
| Prestar o serviço | conteúdo que você cria no produto | execução de contrato | até a exclusão pelo titular ou término do contrato |
| Segurança e trilha de auditoria | registros de acesso, endereço (apenas hash), ações | obrigação legal / legítimo interesse | {{AUDIT_RETENTION_DAYS}} dias |
| Prova de conformidade | registros de consentimento e de solicitações | obrigação legal | {{prazo}} |
| {{Outra}} | {{dados}} | {{base}} | {{prazo}} |

*Gere esta tabela a partir de `python manage.py privacy_ropa` e das finalidades cadastradas.*

## 3. Com quem compartilhamos

{{Lista de operadores/suboperadores ativos: nome, finalidade, país, mecanismo de transferência.}}

**Transferência internacional:** ocorre para {{países}} com base em {{cláusulas-padrão da ANPD /
decisão de adequação / outro mecanismo do art. 33}} (Resolução CD/ANPD 19/2024).

## 4. Seus direitos (art. 18)

Você pode pedir: confirmação do tratamento; acesso; correção; anonimização, bloqueio ou eliminação
de dados desnecessários ou tratados em desacordo com a lei; portabilidade; eliminação dos dados
tratados com consentimento; informação sobre com quem compartilhamos; informação sobre a
possibilidade de não consentir e suas consequências; revogação do consentimento.

Como pedir: {{URL do formulário ou endpoint}} ou {{e-mail do DPO}}. Respondemos em até
{{15}} dias. Pedidos destrutivos exigem confirmação por e-mail.

## 5. Consentimento e cookies

Pedimos consentimento apenas para finalidades que dependem dele, de forma específica e destacada.
Você pode revogá-lo a qualquer momento, com a mesma facilidade com que o deu. Se recusar:
{{consequência de recusar, por finalidade}}. Categorias de cookies: {{necessários, preferências,
análise, marketing}}.

## 6. Crianças e adolescentes

{{O produto não é destinado a menores de 18 anos / Tratamos dados de menores somente com o
consentimento específico de um dos pais ou do responsável e com verificação de idade
adequada (LGPD art. 14; Lei 15.211/2025).}}

## 7. Segurança

Criptografia em trânsito e, para campos sensíveis, em repouso; autenticação em dois fatores;
controle de acesso por organização; trilha de auditoria à prova de adulteração; cópias de
segurança com prazo de retenção de {{prazo}}. Em caso de incidente com risco relevante,
comunicaremos a ANPD e os titulares no prazo da Resolução CD/ANPD 15/2024.

## 8. Mudanças e contato

Avisaremos sobre mudanças relevantes por {{meio}}. Dúvidas ou reclamações: {{DPO}}. Você também
pode reclamar à ANPD (gov.br/anpd).
