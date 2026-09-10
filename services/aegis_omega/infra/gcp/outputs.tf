output "cloud_run_uri" { value = google_cloud_run_v2_service.aegis.uri }
output "telemetry_topic" { value = google_pubsub_topic.telemetry.name }
output "evidence_bucket" { value = google_storage_bucket.evidence.name }
output "analytics_dataset" { value = google_bigquery_dataset.analytics.dataset_id }
