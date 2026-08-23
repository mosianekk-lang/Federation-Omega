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
  description = "Provider-native verified Google Cloud project ID. Do not infer from legacy transport metadata."
  type        = string
}

variable "region" {
  description = "Primary region for command queue and future mesh gateway."
  type        = string
  default     = "africa-south1"
}

variable "environment" {
  description = "Deployment environment label."
  type        = string
  default     = "shadow"
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_service_account" "mesh_gateway" {
  account_id   = "federation-mesh-gateway"
  display_name = "Federation Omni-Mesh Gateway"
  description  = "Least-privilege runtime identity for the Federation Omni-Mesh gateway."
}

resource "google_pubsub_topic" "events" {
  name = "federation-mesh-events-v1"
  labels = {
    system      = "federation-omni-mesh"
    environment = var.environment
  }
}

resource "google_pubsub_topic" "dead_letter" {
  name = "federation-mesh-dead-letter-v1"
  labels = {
    system      = "federation-omni-mesh"
    environment = var.environment
  }
}

resource "google_pubsub_subscription" "router" {
  name  = "federation-mesh-router-v1"
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

resource "google_cloud_tasks_queue" "commands" {
  name     = "federation-mesh-commands-v1"
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
}

resource "google_pubsub_topic_iam_member" "gateway_publish_events" {
  topic  = google_pubsub_topic.events.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.mesh_gateway.email}"
}

resource "google_pubsub_subscription_iam_member" "gateway_consume_events" {
  subscription = google_pubsub_subscription.router.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.mesh_gateway.email}"
}

resource "google_pubsub_topic_iam_member" "gateway_publish_dead_letter" {
  topic  = google_pubsub_topic.dead_letter.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.mesh_gateway.email}"
}

output "mesh_gateway_service_account" {
  value = google_service_account.mesh_gateway.email
}

output "events_topic" {
  value = google_pubsub_topic.events.name
}

output "router_subscription" {
  value = google_pubsub_subscription.router.name
}

output "dead_letter_topic" {
  value = google_pubsub_topic.dead_letter.name
}

output "command_queue" {
  value = google_cloud_tasks_queue.commands.name
}
