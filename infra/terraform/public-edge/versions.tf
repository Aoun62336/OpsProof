terraform {
  required_version = ">= 1.17.0, < 2.0.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "= 6.73.0" }
  }
  backend "s3" {}
}
provider "aws" {
  allowed_account_ids         = var.expected_account_id != "" ? [var.expected_account_id] : null
  skip_credentials_validation = !var.enable_paid_resources
  skip_requesting_account_id  = !var.enable_paid_resources
  skip_metadata_api_check     = true
  region                      = "ap-south-1"
  default_tags {
    tags = { Project = "OpsProof", Environment = "temporary-verification", ManagedBy = "Terraform", CostCenter = "opsproof-cloud" }
  }
}
