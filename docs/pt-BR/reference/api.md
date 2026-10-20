# Endpoints REST

> Gerado por `python scripts/gen_docs.py`. Não edite à mão.

| Método | Caminho | Resumo |
|---|---|---|
| GET | `/api/v1/actions/` | actions_retrieve |
| GET | `/api/v1/actions/actions.changes/` | Actions Changes |
| POST | `/api/v1/actions/actions.changes/` | Actions Changes |
| POST | `/api/v1/actions/actions.undo/` | Actions Undo |
| GET | `/api/v1/actions/flags.evaluate/` | Flags Evaluate |
| POST | `/api/v1/actions/flags.evaluate/` | Flags Evaluate |
| POST | `/api/v1/actions/flows.cancel/` | Flows Cancel |
| GET | `/api/v1/actions/flows.catalog/` | Flows Catalog |
| POST | `/api/v1/actions/flows.catalog/` | Flows Catalog |
| GET | `/api/v1/actions/flows.runs/` | Flows Runs |
| POST | `/api/v1/actions/flows.runs/` | Flows Runs |
| POST | `/api/v1/actions/flows.signal/` | Flows Signal |
| POST | `/api/v1/actions/flows.start/` | Flows Start |
| GET | `/api/v1/actions/flows.status/` | Flows Status |
| POST | `/api/v1/actions/flows.status/` | Flows Status |
| POST | `/api/v1/actions/notes.archive/` | Notes Archive |
| POST | `/api/v1/actions/notes.create/` | Notes Create |
| GET | `/api/v1/actions/notes.get/` | Notes Get |
| POST | `/api/v1/actions/notes.get/` | Notes Get |
| GET | `/api/v1/actions/notes.list/` | Notes List |
| POST | `/api/v1/actions/notes.list/` | Notes List |
| POST | `/api/v1/actions/notes.update/` | Notes Update |
| GET | `/api/v1/actions/settings.get/` | Settings Get |
| POST | `/api/v1/actions/settings.get/` | Settings Get |
| GET | `/api/v1/api-keys/` | api_keys_list |
| POST | `/api/v1/api-keys/` | api_keys_create |
| DELETE | `/api/v1/api-keys/{id}/` | api_keys_destroy |
| GET | `/api/v1/api-keys/{id}/` | api_keys_retrieve |
| POST | `/api/v1/api-keys/{id}/rotate/` | api_keys_rotate_create |
| POST | `/api/v1/api-keys/{id}/rotate{format}` | api_keys_rotate_formatted_create |
| DELETE | `/api/v1/api-keys/{id}{format}` | api_keys_formatted_destroy |
| GET | `/api/v1/api-keys/{id}{format}` | api_keys_formatted_retrieve |
| GET | `/api/v1/api-keys{format}` | api_keys_formatted_list |
| POST | `/api/v1/api-keys{format}` | api_keys_formatted_create |
| GET | `/api/v1/auth/csrf/` | auth_csrf_retrieve |
| POST | `/api/v1/auth/login/` | auth_login_create |
| POST | `/api/v1/auth/logout/` | auth_logout_create |
| GET | `/api/v1/auth/me/` | auth_me_retrieve |
| PATCH | `/api/v1/auth/me/` | auth_me_partial_update |
| GET | `/api/v1/health/live/` | health_live_retrieve |
| GET | `/api/v1/health/ready/` | health_ready_retrieve |
| GET | `/api/v1/notes/` | notes_list |
| POST | `/api/v1/notes/` | notes_create |
| DELETE | `/api/v1/notes/{id}/` | notes_destroy |
| GET | `/api/v1/notes/{id}/` | notes_retrieve |
| PATCH | `/api/v1/notes/{id}/` | notes_partial_update |
| DELETE | `/api/v1/notes/{id}{format}` | notes_formatted_destroy |
| GET | `/api/v1/notes/{id}{format}` | notes_formatted_retrieve |
| PATCH | `/api/v1/notes/{id}{format}` | notes_formatted_partial_update |
| GET | `/api/v1/notes{format}` | notes_formatted_list |
| POST | `/api/v1/notes{format}` | notes_formatted_create |
| GET | `/api/v1/organizations/` | organizations_list |
| POST | `/api/v1/organizations/` | organizations_create |
| GET | `/api/v1/organizations/{id}/` | organizations_retrieve |
| GET | `/api/v1/organizations/{id}{format}` | organizations_formatted_retrieve |
| GET | `/api/v1/organizations{format}` | organizations_formatted_list |
| POST | `/api/v1/organizations{format}` | organizations_formatted_create |
| GET | `/api/v1/privacy/consents/` | privacy_consents_list |
| POST | `/api/v1/privacy/consents/` | privacy_consents_create |
| GET | `/api/v1/privacy/consents/state/` | privacy_consents_state_list |
| GET | `/api/v1/privacy/consents/state{format}` | privacy_consents_state_formatted_list |
| GET | `/api/v1/privacy/consents/{id}/` | privacy_consents_retrieve |
| GET | `/api/v1/privacy/consents/{id}{format}` | privacy_consents_formatted_retrieve |
| GET | `/api/v1/privacy/consents{format}` | privacy_consents_formatted_list |
| POST | `/api/v1/privacy/consents{format}` | privacy_consents_formatted_create |
| GET | `/api/v1/privacy/cookies/` | privacy_cookies_retrieve |
| GET | `/api/v1/privacy/exports/{token}/` | privacy_exports_retrieve |
| GET | `/api/v1/privacy/notice/` | privacy_notice_retrieve |
| POST | `/api/v1/privacy/public/requests/` | privacy_public_requests_create |
| POST | `/api/v1/privacy/public/verify/` | privacy_public_verify_create |
| GET | `/api/v1/privacy/purposes/` | privacy_purposes_list |
| GET | `/api/v1/privacy/purposes/{id}/` | privacy_purposes_retrieve |
| GET | `/api/v1/privacy/purposes/{id}{format}` | privacy_purposes_formatted_retrieve |
| GET | `/api/v1/privacy/purposes{format}` | privacy_purposes_formatted_list |
| GET | `/api/v1/privacy/requests/` | privacy_requests_list |
| POST | `/api/v1/privacy/requests/` | privacy_requests_create |
| GET | `/api/v1/privacy/requests/{id}/` | privacy_requests_retrieve |
| GET | `/api/v1/privacy/requests/{id}{format}` | privacy_requests_formatted_retrieve |
| GET | `/api/v1/privacy/requests{format}` | privacy_requests_formatted_list |
| POST | `/api/v1/privacy/requests{format}` | privacy_requests_formatted_create |
| GET | `/api/v1/privacy/transparency/` | privacy_transparency_retrieve |
| GET | `/api/v1/uploads/` | uploads_list |
| POST | `/api/v1/uploads/` | uploads_create |
| DELETE | `/api/v1/uploads/{id}/` | uploads_destroy |
| GET | `/api/v1/uploads/{id}/` | uploads_retrieve |
| GET | `/api/v1/uploads/{id}/download/` | uploads_download_retrieve |
| GET | `/api/v1/uploads/{id}/download{format}` | uploads_download_formatted_retrieve |
| DELETE | `/api/v1/uploads/{id}{format}` | uploads_formatted_destroy |
| GET | `/api/v1/uploads/{id}{format}` | uploads_formatted_retrieve |
| GET | `/api/v1/uploads{format}` | uploads_formatted_list |
| POST | `/api/v1/uploads{format}` | uploads_formatted_create |
| GET | `/api/v1/webhooks/deliveries/` | webhooks_deliveries_list |
| POST | `/api/v1/webhooks/deliveries/` | webhooks_deliveries_create |
| GET | `/api/v1/webhooks/deliveries/{id}/` | webhooks_deliveries_retrieve |
| POST | `/api/v1/webhooks/deliveries/{id}/redeliver/` | webhooks_deliveries_redeliver_create |
| POST | `/api/v1/webhooks/deliveries/{id}/redeliver{format}` | webhooks_deliveries_redeliver_formatted_create |
| GET | `/api/v1/webhooks/deliveries/{id}{format}` | webhooks_deliveries_formatted_retrieve |
| GET | `/api/v1/webhooks/deliveries{format}` | webhooks_deliveries_formatted_list |
| POST | `/api/v1/webhooks/deliveries{format}` | webhooks_deliveries_formatted_create |
| GET | `/api/v1/webhooks/endpoints/` | webhooks_endpoints_list |
| POST | `/api/v1/webhooks/endpoints/` | webhooks_endpoints_create |
| DELETE | `/api/v1/webhooks/endpoints/{id}/` | webhooks_endpoints_destroy |
| GET | `/api/v1/webhooks/endpoints/{id}/` | webhooks_endpoints_retrieve |
| PATCH | `/api/v1/webhooks/endpoints/{id}/` | webhooks_endpoints_partial_update |
| POST | `/api/v1/webhooks/endpoints/{id}/rotate-secret/` | webhooks_endpoints_rotate_secret_create |
| POST | `/api/v1/webhooks/endpoints/{id}/rotate-secret{format}` | webhooks_endpoints_rotate_secret_formatted_create |
| POST | `/api/v1/webhooks/endpoints/{id}/test/` | webhooks_endpoints_test_create |
| POST | `/api/v1/webhooks/endpoints/{id}/test{format}` | webhooks_endpoints_test_formatted_create |
| DELETE | `/api/v1/webhooks/endpoints/{id}{format}` | webhooks_endpoints_formatted_destroy |
| GET | `/api/v1/webhooks/endpoints/{id}{format}` | webhooks_endpoints_formatted_retrieve |
| PATCH | `/api/v1/webhooks/endpoints/{id}{format}` | webhooks_endpoints_formatted_partial_update |
| GET | `/api/v1/webhooks/endpoints{format}` | webhooks_endpoints_formatted_list |
| POST | `/api/v1/webhooks/endpoints{format}` | webhooks_endpoints_formatted_create |
