provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "OpsProof"
      Environment = "temporary-verification"
      ManagedBy   = "Terraform"
      CostCenter  = "opsproof-ephemeral"
      Owner       = var.owner_tag
    }
  }
}
