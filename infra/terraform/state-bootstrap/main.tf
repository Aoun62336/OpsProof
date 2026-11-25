terraform {
  required_version = ">= 1.17.0, < 2.0.0"
  required_providers { aws = { source = "hashicorp/aws", version = "= 6.73.0" } }
}
provider "aws" {
  allowed_account_ids         = var.expected_account_id != "" ? [var.expected_account_id] : null
  skip_credentials_validation = !var.enable_paid_resources
  skip_requesting_account_id  = !var.enable_paid_resources
  skip_metadata_api_check     = true
  region                      = "ap-south-1"
  default_tags { tags = { Project = "OpsProof", ManagedBy = "Terraform", Environment = "temporary-state-bootstrap" } }
}
variable "enable_paid_resources" {
  type    = bool
  default = false
}
variable "bucket_name" {
  type    = string
  default = ""
}
variable "approval_reference" {
  type    = string
  default = ""
}
variable "approval_acknowledgement" {
  type      = string
  default   = ""
  sensitive = true
}
variable "expected_account_id" {
  type    = string
  default = ""
  validation {
    condition     = var.expected_account_id == "" || can(regex("^[0-9]{12}$", var.expected_account_id))
    error_message = "Provide the exact approved twelve-digit AWS account."
  }
}
data "aws_caller_identity" "current" {
  count = var.enable_paid_resources ? 1 : 0
}
resource "aws_s3_bucket" "state" {
  count  = var.enable_paid_resources ? 1 : 0
  bucket = var.bucket_name
  lifecycle {
    precondition {
      condition     = var.expected_account_id != "" && data.aws_caller_identity.current[0].account_id == var.expected_account_id && var.approval_acknowledgement == "I_APPROVE_TEMPORARY_OPSPROOF_AWS_CHARGES" && length(var.bucket_name) >= 16 && length(var.approval_reference) >= 12
      error_message = "State bootstrap requires an explicitly approved, globally unique bucket and signed-off estimate."
    }
  }
}
resource "aws_s3_bucket_public_access_block" "state" {
  count                   = var.enable_paid_resources ? 1 : 0
  bucket                  = aws_s3_bucket.state[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_versioning" "state" {
  count  = var.enable_paid_resources ? 1 : 0
  bucket = aws_s3_bucket.state[0].id
  versioning_configuration { status = "Enabled" }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  count  = var.enable_paid_resources ? 1 : 0
  bucket = aws_s3_bucket.state[0].id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
resource "aws_s3_bucket_policy" "state_tls_only" {
  count  = var.enable_paid_resources ? 1 : 0
  bucket = aws_s3_bucket.state[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyUnencryptedTransport", Effect = "Deny", Principal = "*"
      Action    = "s3:*", Resource = [aws_s3_bucket.state[0].arn, "${aws_s3_bucket.state[0].arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
  depends_on = [aws_s3_bucket_public_access_block.state]
}
output "bucket" { value = var.enable_paid_resources ? aws_s3_bucket.state[0].bucket : null }
