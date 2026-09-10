locals { required_services = toset(["run.googleapis.com","pubsub.googleapis.com","bigquery.googleapis.com","firestore.googleapis.com","storage.googleapis.com","secretmanager.googleapis.com","cloudkms.googleapis.com","artifactregistry.googleapis.com","cloudbuild.googleapis.com","logging.googleapis.com","monitoring.googleapis.com"]) }
resource "google_project_service" "apis" { for_each = local.required_services project = var.project_id service = each.value disable_on_destroy = false }
resource "google_service_account" "runtime" { project = var.project_id account_id = "aegis-omega-runtime" display_name = "AEGIS Omega runtime" }
resource "google_pubsub_topic" "telemetry" { project = var.project_id name = "aegis-omega-telemetry" }
resource "google_bigquery_dataset" "analytics" { project = var.project_id dataset_id = "aegis_omega" location = var.region delete_contents_on_destroy = false }
resource "google_storage_bucket" "evidence" { project = var.project_id name = "${var.project_id}-aegis-omega-evidence" location = var.region uniform_bucket_level_access = true versioning { enabled = true } lifecycle_rule { condition { age = 365 } action { type = "Delete" } } }
resource "google_secret_manager_secret" "hmac" { project = var.project_id secret_id = "aegis-omega-hmac" replication { auto {} } }
resource "google_kms_key_ring" "aegis" { project = var.project_id name = "aegis-omega" location = var.region }
resource "google_kms_crypto_key" "evidence" { name = "evidence" key_ring = google_kms_key_ring.aegis.id rotation_period = "7776000s" }
resource "google_project_iam_member" "firestore_user" { project = var.project_id role = "roles/datastore.user" member = "serviceAccount:${google_service_account.runtime.email}" }
resource "google_project_iam_member" "pubsub_publisher" { project = var.project_id role = "roles/pubsub.publisher" member = "serviceAccount:${google_service_account.runtime.email}" }
resource "google_storage_bucket_iam_member" "evidence_creator" { bucket = google_storage_bucket.evidence.name role = "roles/storage.objectCreator" member = "serviceAccount:${google_service_account.runtime.email}" }
resource "google_secret_manager_secret_iam_member" "hmac_reader" { project = var.project_id secret_id = google_secret_manager_secret.hmac.secret_id role = "roles/secretmanager.secretAccessor" member = "serviceAccount:${google_service_account.runtime.email}" }
resource "google_cloud_run_v2_service" "aegis" {
  project = var.project_id location = var.region name = var.service_name deletion_protection = true ingress = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
  template {
    service_account = google_service_account.runtime.email
    containers {
      image = var.container_image
      env { name = "AEGIS_ENV" value = "production" }
      env { name = "AEGIS_CASE_STORE" value = "firestore" }
      env { name = "AEGIS_GCP_PROJECT" value = var.project_id }
      env { name = "AEGIS_PUBSUB_TOPIC" value = google_pubsub_topic.telemetry.name }
      env { name = "AEGIS_EVIDENCE_BUCKET" value = google_storage_bucket.evidence.name }
      env { name = "AEGIS_HMAC_KEY_ID" value = "${google_secret_manager_secret.hmac.secret_id}:${var.hmac_secret_version}" }
      env {
        name = "AEGIS_HMAC_SECRET"
        value_source { secret_key_ref { secret = google_secret_manager_secret.hmac.secret_id version = var.hmac_secret_version } }
      }
      resources { limits = { cpu = "1", memory = "512Mi" } }
    }
    scaling { min_instance_count = 0 max_instance_count = 20 }
  }
  depends_on = [google_project_service.apis]
}
