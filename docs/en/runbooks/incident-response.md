# Personal-data incident response

[Versão em português](../../pt-BR/runbooks/resposta-incidentes.md)

1. **Triage and contain:** open a restricted incident record, assign commander/DPO/legal/tech
   owners, stop ongoing exposure, rotate compromised credentials, and preserve immutable
   evidence. Do not paste personal data into chat, tickets, logs, or Sentry.
2. **Establish facts:** record discovery/confirmation times, systems, data categories, subject
   count, geography, encryption/key exposure, unauthorized access/exfiltration, and current
   containment confidence.
3. **Assess:** controller and qualified privacy/legal owners determine whether the confirmed
   incident involves LGPD personal data and may cause relevant risk or harm. Set the legally
   reviewed deadline; Resolution 15/2024 generally uses three business days.
4. **Notify when required:** prepare ANPD and direct subject communications in clear Portuguese,
   including nature/categories, protections, risks, discovery date, mitigation, and DPO contact.
   Record notification timestamps and approved copies.
5. **Recover:** eradicate the cause, restore safely, increase monitoring, validate tenant/data
   boundaries, and communicate status without speculation.
6. **Learn and retain:** complete root-cause and corrective-action reviews. Track owners/dates,
   verify fixes, update the RIPD/threat model, and retain the incident record for at least five
   years.

If Fly, PostgreSQL, Tigris, Upstash, Sentry, or another processor is involved, preserve their
case IDs and notices and activate contractual incident-cooperation terms.
