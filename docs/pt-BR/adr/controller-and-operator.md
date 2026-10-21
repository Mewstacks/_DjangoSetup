# ADR 17: Quem é o controlador, e de quem é a solicitação

**Status:** aceito como orientação; o modelo de dados **ainda não** é dividido por papel.

## Contexto

A LGPD distingue o **controlador** (decide finalidades e meios) do **operador** (trata em nome do
controlador) (arts. 5º, 37, 39, 42). Num produto multi-tenant os dois aparecem:

- Para as contas, a cobrança e os registros de segurança dos seus próprios clientes, **o dono da
  plataforma é o controlador**.
- Para os dados que os membros de uma organização cliente colocam no produto, **a organização cliente
  é a controladora** e o dono da plataforma o **operador**.

`DataSubject` e `DataSubjectRequest` da plataforma são globais, não escopados a uma organização: uma
pessoa, um registro, um lugar para pedir.

## Decisão

- Documentar a divisão (este ADR, o guia de encerramento, o modelo de acordo de tratamento) e fazer o
  contrato com o cliente declará-la. O código não a decide.
- Manter as solicitações globais para dados em que **a plataforma é controladora**. Para dados em que
  ela é **operadora**, o dono da plataforma encaminha a solicitação à organização cliente (o acordo fixa
  o prazo) e fornece os executores (exportar, eliminar, bloquear) que a organização usa.
- Adiar um perfil de privacidade por organização (nome do controlador, DPO, URL do aviso por tenant)
  até que um cliente precise publicar o próprio: o endpoint de transparência publica o do dono da
  plataforma.

## Consequências

- A eliminação de uma pessoa alcança toda organização a que ela pertence, porque a pessoa é global.
  Um produto em que uma pessoa pode ser membro de clientes não relacionados deve decidir, com um
  advogado, se uma solicitação de um membro de um cliente pode tocar dados de outro. O padrão (não pode
  para dados de operador; pode para dados de controlador) precisa de uma marca por modelo no catálogo se
  você precisar dessa precisão.
- Este é o ponto que mais merece o tempo de um advogado antes do primeiro cliente.
