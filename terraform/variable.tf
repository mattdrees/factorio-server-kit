variable "project_id" {
  type = string
}

# Fully-qualified factorio-starter image to deploy. deploy.sh sets this (via
# TF_VAR_factorio_starter_image) to the freshly-built image's digest so a code
# change produces a new image reference and Terraform rolls a new Cloud Run
# revision. Defaults to the floating :latest tag when unset, in which case
# `terraform apply` alone will NOT pick up rebuilt code (no diff) -- use
# deploy.sh for that.
variable "factorio_starter_image" {
  type    = string
  default = ""
}
