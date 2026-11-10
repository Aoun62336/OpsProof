terraform {
  required_version = ">= 1.17.0, < 2.0.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = ">= 6.0, < 7.0" }
  }
  # The S3 backend MUST be bootstrapped separately with versioning and native locks.
  # For offline validation: terraform init -backend=false (does not create AWS resources).
  backend "s3" {}
}
