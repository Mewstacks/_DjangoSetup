# Acordo de Tratamento de Dados Pessoais (operador)

> **Modelo, não aconselhamento jurídico.** Use quando o **cliente** é o controlador e você, o
> operador (LGPD arts. 5º, 37, 39 e 42). Peça revisão de um advogado. Versão {{versão}}.

**Controlador (Cliente):** {{razão social, CNPJ}}. **Operador ({{Empresa}}):** {{razão social, CNPJ}}.
**Encarregado do operador:** {{nome, contato}}.

## 1. Objeto e instruções

O Operador trata dados pessoais **somente** para prestar o serviço contratado e conforme as
instruções documentadas do Controlador (este acordo, o contrato e as configurações do produto).
Se uma instrução violar a lei, o Operador avisará o Controlador.

## 2. Dados e titulares

| Categoria de titulares | Categorias de dados | Natureza e finalidade | Duração |
|---|---|---|---|
| {{usuários do cliente}} | {{identificação, contato, conteúdo}} | {{armazenar e processar}} | vigência do contrato + {{prazo}} |

Dados pessoais sensíveis: {{não tratados / quais}}. Dados de crianças e adolescentes: {{não / sob regras do art. 14}}.

## 3. Obrigações do Operador

1. Confidencialidade: pessoas autorizadas obrigadas a sigilo.
2. Segurança (art. 46): medidas descritas no Anexo I.
3. Suboperadores: lista no Anexo II; aviso prévio de {{prazo}} para mudanças, com direito de oposição.
4. Direitos dos titulares: o Operador encaminha ao Controlador solicitações recebidas em até
   {{3}} dias úteis e fornece ferramentas para atendê-las (acesso, exportação, eliminação, bloqueio).
5. Incidentes: o Operador comunica o Controlador sem demora injustificada, em até {{48}} horas após
   a ciência, com as informações que possuir (natureza, dados, titulares, medidas), para que o
   Controlador cumpra o art. 48 e a Resolução CD/ANPD 15/2024.
6. Auditoria: o Operador fornece informações para demonstrar conformidade e permite auditorias
   razoáveis, mediante aviso e sigilo.
7. Transferência internacional: somente com mecanismo do art. 33 (Resolução CD/ANPD 19/2024).

## 4. Término

Ao término, o Operador devolve os dados em formato estruturado e os elimina em {{prazo}}, salvo
obrigação legal de guarda, e declara a eliminação por escrito. Cópias de segurança expiram em
{{prazo}}.

## 5. Responsabilidade

{{Conforme o contrato; art. 42 da LGPD sobre responsabilidade solidária do operador que descumpre
a lei ou as instruções lícitas.}}

## Anexo I — Medidas de segurança

Criptografia em trânsito e em repouso (campos sensíveis); autenticação em dois fatores;
isolamento lógico por organização; registro de auditoria com cadeia de hash; segregação de
funções do banco de dados; backups; testes de restauração {{periodicidade}}; gestão de
vulnerabilidades e dependências; resposta a incidentes (runbooks).

## Anexo II — Suboperadores

{{Gerar da lista de `SubProcessor` ativos: nome, finalidade, país, mecanismo de transferência.}}
