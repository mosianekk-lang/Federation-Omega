terraform {
  required_version = ">= 1.6.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 6.0"
    }
  }
}

variable "project_id" {
  description = "Provider-native verified Google Cloud project ID. Never infer this value from legacy bridge metadata."
  type        = string
}

variable "region" {
  description = "Primary region for the shadow command queue and mesh gateway."
  type        = string
  default     = "africa-south1"
}

variable "environment" {
  description = "Deployment environment label. Production is forbidden before all proof gates pass."
  type        = string
  default     = "shadow"

  validation {
    condition     = contains(["shadow", "canary", "staging", "production"], var.environment)
    error_message = "environment must be shadow, canary, staging, or production."
  }
}

variable "gateway_image" {
  description = "Immutable container image reference for the mesh gateway. A digest is required; mutable :latest tags are rejected."
  type        = string

  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.gateway_image))
    error_message = "gateway_image must be pinned by sha256 digest."
  }
}

variable "ledger_backend_uri" {
  description = "Private durable transactional ledger backend URI. This is a reference, not a credential."
  type        = string

  validation {
    condition     = length(trimspace(var.ledger_backend_uri)) > 0
    error_message = "ledger_backend_uri is required before provider deployment."
  }
}

variable "receipt_sink_uri" {
  description = "Private append-only receipt/evidence sink URI. This is a reference, not a credential."
  type        = string

  validation {
    condition     = length(trimspace(var.receipt_sink_uri)) > 0
    error_message = "receipt_sink_uri is required before provider deployment."
  }
}

variable "gateway_min_instances" {
  description = "Minimum Cloud Run instances. Shadow defaults to zero."
  type        = number
  default     = 0

  validation {
    condition     = var.gateway_min_instances >= 0
    error_message = "gateway_min_instances must be non-negative."
  }
}

variable "gateway_max_instances" {
  description = "Maximum Cloud Run instances for the bounded shadow/canary."
  type        = number
  default     = 2

  validation {
    condition     = var.gateway_max_instances >= 1
    error_message = "gateway_max_instances must be at least one."
  }
}

variable "deletion_protection" {
  description = "Protect the gateway from accidental deletion. Disable only for a separately approved rollback/destroy canary."
  type        = bool
  default     = true
}

provider "google" {
  project = var.project_id
  region  = var.region
}

data "google_project" "current" {
  project_id = var.project_id
}

locals {
  name_suffix = var.environment
  required_services = toset([
    "artifactregistry.googleapis.com",
    "cloudtasks.googleapis.com",
    "iamcredentials.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "pubsub.googleapis.com",
    "run.googleapis.com",
    "sts.googleapis.com",
  ])
  pubsub_service_agent = "service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_project_service" "required" {
  for_each = local.required_services

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_service_account" "mesh_gateway" {
  account_id   = "federation-mesh-gateway"
  display_name = "Federation Omni-Mesh Gateway"
  description  = "Least-privilege runtime identity for the Federation Omni-Mesh gateway."

  depends_on = [google_project_service.required]
}

resource "google_service_account" "task_dispatcher" {
  account_id   = "federation-mesh-task-dispatcher"
  display_name = "Federation Omni-Mesh Task Dispatcher"
  description  = "OIDC identity used only by Cloud Tasks to invoke the private mesh gateway."

  depends_on = [google_project_service.required]
}

resource "google_pubsub_topic" "events" {
  name = "federation-mesh-events-v1-${local.name_suffix}"
  labels = {
    system      = "federation-omni-mesh"
    environment = var.environment
  }

  depends_on = [google_project_service.required]
}

resource "google_pubsub_topic" "receipts" {
  name = "federation-mesh-receipts-v1-${local.name_suffix}"
  labels = {
    system      = "federation-omni-mesh"
    environment = var.environment
  }

  depends_on = [google_project_service.required]
}

resource "google_pubsub_topic" "dead_letter" {
  name = "federation-mesh-dead-letter-v1-${local.name_suffix}"
  labels = {
    system      = "federation-omni-mesh"
    environment = var.environment
  }

  depends_on = [google_project_service.required]
}

resource "google_pubsub_subscription" "router" {
  name  = "federation-mesh-router-v1-${local.name_suffix}"
  topic = google_pubsub_topic.events.id

  ack_deadline_seconds       = 30
  message_retention_duration = "604800s"
  retain_acked_messages      = false

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "300s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letter.id
    max_delivery_attempts = 5
  }

  expiration_policy {
    ttl = ""
  }
}

resource "google_pubsub_subscription" "dead_letter_reader" {
  name  = "federation-mesh-dead-letter-reader-v1-${local.name_suffix}"
  topic = google_pubsub_topic.dead_letter.id

  ack_deadline_seconds       = 30
  message_retention_duration = "1209600s"

  expiration_policy {
    ttl = ""
  }
}

resource "google_pubsub_subscription" "receipt_reader" {
  name  = "federation-mesh-receipt-reader-v1-${local.name_suffix}"
  topic = google_pubsub_topic.receipts.id

  ack_deadline_seconds       = 30
  message_retention_duration = "1209600s"

  expiration_policy {
    ttl = ""
  }
}

resource "google_pubsub_topic_iam_member" "gateway_publish_events" {
  topic  = google_pubsub_topic.events.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.mesh_gateway.email}"
}

resource "google_pubsub_topic_iam_member" "gateway_publish_receipts" {
  topic  = google_pubsub_topic.receipts.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.mesh_gateway.email}"
}

resource "google_pubsub_subscription_iam_member" "gateway_consume_events" {
  subscription = google_pubsub_subscription.router.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.mesh_gateway.email}"
}

resource "google_pubsub_subscription_iam_member" "gateway_consume_dead_letter" {
  subscription = google_pubsub_subscription.dead_letter_reader.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.mesh_gateway.email}"
}

resource "google_pubsub_subscription_iam_member" "gateway_consume_receipts" {
  subscription = google_pubsub_subscription.receipt_reader.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.mesh_gateway.email}"
}

# Pub/Sub's service agent must be able to forward and acknowledge
# undeliverable messages for the dead-letter policy to operate.
resource "google_pubsub_topic_iam_member" "pubsub_service_agent_publish_dead_letter" {
  topic  = google_pubsub_topic.dead_letter.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${local.pubsub_service_agent}"
}

resource "google_pubsub_subscription_iam_member" "pubsub_service_agent_ack_source" {
  subscription = google_pubsub_subscription.router.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${local.pubsub_service_agent}"
}

resource "google_cloud_tasks_queue" "commands" {
  name     = "federation-mesh-commands-v1-${local.name_suffix}"
  location = var.region

  rate_limits {
    max_concurrent_dispatches = 20
    max_dispatches_per_second = 10
  }

  retry_config {
    max_attempts       = 5
    max_retry_duration = "3600s"
    min_backoff        = "5s"
    max_backoff        = "300s"
    max_doublings      = 5
  }

  depends_on = [google_project_service.required]
}

resource "google_cloud_run_v2_service" "gateway" {
  name                = "federation-mesh-gateway-${local.name_suffix}"
  location            = var.region
  deletion_protection = var.deletion_protection
  ingress             = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.mesh_gateway.email
    timeout         = "300s"

    scaling {
      min_instance_count = var.gateway_min_instances
      max_instance_count = var.gateway_max_instances
    }

    containers {
      image = var.gateway_image

      env {
        name  = "MESH_ENVIRONMENT"
        value = var.environment
      }

      env {
        name  = "MESH_EVENTS_TOPIC"
        value = google_pubsub_topic.events.id
      }

      env {
        name  = "MESH_RECEIPTS_TOPIC"
        value = google_pubsub_topic.receipts.id
      }

      env {
        name  = "MESH_COMMAND_QUEUE"
        value = google_cloud_tasks_queue.commands.id
      }

      env {
        name  = "MESH_LEDGER_BACKEND_URI"
        value = var.ledger_backend_uri
      }

      env {
        name  = "MESH_RECEIPT_SINK_URI"
        value = var.receipt_sink_uri
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle = true
      }
    }

    max_instance_request_concurrency = 20
  }

  lifecycle {
    precondition {
      condition     = var.environment != "production"
      error_message = "Production deployment is prohibited until the CFBE/JARVIS/Sentinel terminal gates pass and the module is deliberately revised."
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_cloud_run_v2_service_iam_member" "task_dispatcher_invoker" {
  project  = var.project_id
  location = google_cloud_run_v2_service.gateway.location
  name     = google_cloud_run_v2_service.gateway.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.task_dispatcher.email}"
}

resource "google_service_account_iam_member" "gateway_can_act_as_task_dispatcher" {
  service_account_id = google_service_account.task_dispatcher.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.mesh_gateway.email}"
}

resource "google_cloud_tasks_queue_iam_member" "gateway_enqueue_commands" {
  project  = var.project_id
  location = google_cloud_tasks_queue.commands.location
  name     = google_cloud_tasks_queue.commands.name
  role     = "roles/cloudtasks.enqueuer"
  member   = "serviceAccount:${google_service_account.mesh_gateway.email}"
}

output "verified_project_number" {
  value = data.google_project.current.number
}

output "mesh_gateway_service_account" {
  value = google_service_account.mesh_gateway.email
}

output "task_dispatcher_service_account" {
  value = google_service_account.task_dispatcher.email
}

output "mesh_gateway_uri" {
  value = google_cloud_run_v2_service.gateway.uri
}

output "events_topic" {
  value = google_pubsub_topic.events.name
}

output "receipt_topic" {
  value = google_pubsub_topic.receipts.name
}

output "router_subscription" {
  value = google_pubsub_subscription.router.name
}

output "dead_letter_topic" {
  value = google_pubsub_topic.dead_letter.name
}

output "dead_letter_subscription" {
  value = google_pubsub_subscription.dead_letter_reader.name
}

output "command_queue" {
  value = google_cloud_tasks_queue.commands.name
}

output "task_oidc_audience" {
  value = google_cloud_run_v2_service.gateway.uri
}
