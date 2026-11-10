locals { name = "opsproof-verify" }

data "aws_caller_identity" "active" { count = var.enable_paid_resources ? 1 : 0 }
data "aws_availability_zones" "available" {
  count = var.enable_paid_resources ? 1 : 0
  state = "available"
}

resource "terraform_data" "cloud_gate" {
  count = var.enable_paid_resources ? 1 : 0
  input = var.approval_reference
  lifecycle {
    precondition {
      condition = (
        var.approval_acknowledgement == "I_APPROVE_TEMPORARY_OPSPROOF_AWS_CHARGES" &&
        length(var.approval_reference) >= 8 &&
        var.expected_account_id == data.aws_caller_identity.active[0].account_id &&
        var.operator_cidr != "" && var.operator_cidr != "0.0.0.0/0" &&
        var.operator_role_arn != "" &&
        var.kubernetes_version != "" &&
        length(data.aws_availability_zones.available[0].names) >= 2
      )
      error_message = "Cloud gate refused: approval, AWS account, operator /32, IAM role, version and two AZs are mandatory."
    }
  }
}

module "network" {
  count      = var.enable_paid_resources ? 1 : 0
  source     = "./modules/networking"
  name       = local.name
  azs        = slice(data.aws_availability_zones.available[0].names, 0, 2)
  depends_on = [terraform_data.cloud_gate]
}
module "iam" {
  count      = var.enable_paid_resources ? 1 : 0
  source     = "./modules/iam"
  name       = local.name
  depends_on = [terraform_data.cloud_gate]
}
module "eks" {
  count              = var.enable_paid_resources ? 1 : 0
  source             = "./modules/eks"
  name               = local.name
  kubernetes_version = var.kubernetes_version
  vpc_id             = module.network[0].vpc_id
  subnet_ids         = module.network[0].public_subnet_ids
  allowed_cidr       = var.operator_cidr
  node_instance_type = var.node_instance_type
  node_role_arn      = module.iam[0].node_role_arn
  ebs_role_arn       = module.iam[0].ebs_role_arn
  operator_role_arn  = var.operator_role_arn
  depends_on         = [terraform_data.cloud_gate, module.iam]
}

# Optional read-only GitHub access. No AWS provisioning or Kubernetes write permissions.
resource "aws_iam_role" "github_inspect" {
  count = var.enable_paid_resources && var.enable_github_inspection_role ? 1 : 0
  name  = "${local.name}-github-inspect"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = var.github_oidc_provider_arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = { StringEquals = {
        "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        "token.actions.githubusercontent.com:sub" = var.github_oidc_subject
      } }
    }]
  })
  lifecycle {
    precondition {
      condition     = can(regex("^arn:aws:iam::[0-9]{12}:oidc-provider/token\\.actions\\.githubusercontent\\.com$", var.github_oidc_provider_arn)) && startswith(var.github_oidc_subject, "repo:") && !strcontains(var.github_oidc_subject, "*")
      error_message = "Supply exact, verified GitHub OIDC provider ARN and immutable/legacy subject; no wildcard permitted."
    }
  }
}
resource "aws_iam_role_policy" "github_inspect" {
  count = var.enable_paid_resources && var.enable_github_inspection_role ? 1 : 0
  role  = aws_iam_role.github_inspect[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["eks:DescribeCluster"]
      Resource = module.eks[0].cluster_arn
    }]
  })
}
