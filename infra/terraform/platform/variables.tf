variable "region" {
  type    = string
  default = "ap-south-1"
  validation {
    condition     = var.region == "ap-south-1"
    error_message = "The cost-reviewed M7 environment is restricted to ap-south-1."
  }
}
variable "owner_tag" {
  type    = string
  default = "opsproof"
}
variable "enable_paid_resources" {
  type    = bool
  default = false
}
variable "expected_account_id" {
  type    = string
  default = ""
  validation {
    condition     = var.expected_account_id == "" || can(regex("^[0-9]{12}$", var.expected_account_id))
    error_message = "expected_account_id must be an exact 12-digit AWS account ID."
  }
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
variable "maximum_approved_hours" {
  type    = number
  default = 0
  validation {
    condition     = var.maximum_approved_hours == 0 || (var.maximum_approved_hours > 0 && var.maximum_approved_hours <= 12)
    error_message = "Only a verified, explicitly approved 1-12-hour cloud window is supported."
  }
}
variable "gross_budget_usd" {
  type    = number
  default = 0
  validation {
    condition     = var.gross_budget_usd == 0 || (var.gross_budget_usd > 0 && var.gross_budget_usd <= 40)
    error_message = "M7 gross budget may not exceed $40, independently of credits."
  }
}
variable "operator_public_cidr" {
  type    = string
  default = ""
  validation {
    condition     = var.operator_public_cidr == "" || (can(cidrhost(var.operator_public_cidr, 0)) && endswith(var.operator_public_cidr, "/32") && !startswith(var.operator_public_cidr, "0.0.0.0"))
    error_message = "Provide the actual approved public IPv4 /32, not a broad network."
  }
}
variable "operator_role_arn" {
  type    = string
  default = ""
}
variable "kubernetes_version" {
  type    = string
  default = ""
  validation {
    condition     = var.kubernetes_version == "" || can(regex("^1\\.[0-9]{2}$", var.kubernetes_version))
    error_message = "Select a currently supported EKS standard-support version."
  }
}
variable "availability_zones" {
  type    = list(string)
  default = []
  validation {
    condition     = length(var.availability_zones) == 0 || (length(var.availability_zones) == 2 && var.availability_zones[0] != var.availability_zones[1] && alltrue([for az in var.availability_zones : startswith(az, "ap-south-1")]))
    error_message = "Provide two distinct, verified ap-south-1 Availability Zones."
  }
}
variable "node_instance_type" {
  type    = string
  default = "m7i-flex.large"
  validation {
    condition     = var.node_instance_type == "m7i-flex.large"
    error_message = "The selected deployment is exactly two m7i-flex.large workers."
  }
}
variable "alb_controller_policy_file" {
  type        = string
  default     = ""
  description = "Absolute path to reviewed official AWS Load Balancer Controller IAM JSON, pinned by checked upstream version."
}

variable "bootstrap_cni_node_policy" {
  type        = bool
  default     = true
  description = "TRUE only during first EKS bootstrap. MUST be false and reapplied after verified aws-node Pod Identity."
}

variable "bootstrap_master_secret_access" {
  type        = bool
  default     = false
  description = "Temporarily permit ESO access to RDS master secret for one-time credential bootstrap. MUST be false afterward."
}

variable "postgres_engine_version" {
  type        = string
  default     = ""
  description = "Exact PostgreSQL 18 minor tested locally and confirmed orderable in Mumbai before apply."
  validation {
    condition     = var.postgres_engine_version == "" || can(regex("^18\\.[0-9]+$", var.postgres_engine_version))
    error_message = "Pin a verified PostgreSQL 18 minor version."
  }
}
variable "addon_versions" {
  type        = map(string)
  default     = {}
  description = "Exact EKS-compatible versions captured by the read-only account preflight."
  validation {
    condition     = alltrue([for name, version in var.addon_versions : contains(["eks-pod-identity-agent", "vpc-cni", "kube-proxy", "coredns", "aws-ebs-csi-driver", "metrics-server"], name) && can(regex("^v[0-9]+\\.[0-9]+\\.[0-9]+-eksbuild\\.[0-9]+$", version))])
    error_message = "Provide only exact EKS build versions for the six declared add-ons."
  }
}
