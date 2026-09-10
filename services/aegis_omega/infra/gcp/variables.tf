variable "project_id" { type = string }
variable "region" { type = string default = "africa-south1" }
variable "service_name" { type = string default = "aegis-omega" }
variable "container_image" { type = string }

variable "hmac_secret_version" {
  description = "Immutable enabled Secret Manager version ID for AEGIS provenance HMAC. Never use latest in production."
  type = string
}
