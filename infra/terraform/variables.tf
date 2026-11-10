variable "aws_region" {
  type        = string
  description = "AWS Region explicitly chosen after price/service checks."
  default     = "ap-south-1"
  validation {
    condition     = can(regex("^[a-z]{2}-[a-z]+-[0-9]+$", var.aws_region))
    error_message = "Use a valid AWS Region code."
  }
}
variable "owner_tag" {
  type        = string
  description = "Non-sensitive owner label used for cost inventory."
  default     = "opsproof"
}
variable "enable_paid_resources" {
  type        = bool
  description = "FALSE by default. Enables paid EKS, EC2 and EBS-associated resources only after external approval."
  default     = false
}
variable "approval_acknowledgement" {
  type        = string
  description = "Secondary guard, NOT a substitute for explicit human AWS cost approval."
  default     = ""
  sensitive   = true
}
variable "approval_reference" {
  type        = string
  description = "Reference to a reviewed, externally approved cost estimate."
  default     = ""
}
variable "expected_account_id" {
  type        = string
  description = "The exact twelve-digit AWS account approved for temporary verification."
  default     = ""
  validation {
    condition     = var.expected_account_id == "" || can(regex("^[0-9]{12}$", var.expected_account_id))
    error_message = "expected_account_id must be a twelve-digit AWS account ID."
  }
}
variable "operator_cidr" {
  type        = string
  description = "Current operator public IPv4 /32, never 0.0.0.0/0."
  default     = ""
  validation {
    condition     = var.operator_cidr == "" || (can(cidrhost(var.operator_cidr, 0)) && endswith(var.operator_cidr, "/32"))
    error_message = "Provide one operator IPv4 /32, not an unrestricted or broad CIDR."
  }
}
variable "operator_role_arn" {
  type        = string
  description = "Dedicated IAM role granted cluster-scoped bootstrap EKS access for short-lived local verification."
  default     = ""
}
variable "kubernetes_version" {
  type        = string
  description = "Explicit supported EKS version checked in the chosen Region before apply."
  default     = ""
  validation {
    condition     = var.kubernetes_version == "" || can(regex("^1\\.[0-9]{2}$", var.kubernetes_version))
    error_message = "Use an explicit Kubernetes version such as 1.35 after verification."
  }
}
variable "node_instance_type" {
  type        = string
  description = "Cost-approved single x86_64 worker shape; capacity must support actual Pods."
  default     = "t3.large"
  validation {
    condition     = contains(["t3.large", "t3.xlarge", "m6i.large", "m7i.large"], var.node_instance_type)
    error_message = "Only reviewed x86_64 instance shapes may be used in this profile."
  }
}
variable "enable_github_inspection_role" {
  type        = bool
  default     = false
  description = "Optional narrowly scoped CI EKS describe role. Does NOT grant terraform apply."
}
variable "github_oidc_provider_arn" {
  type        = string
  default     = ""
  description = "Pre-existing, separately verified GitHub OIDC IAM provider ARN."
}
variable "github_oidc_subject" {
  type        = string
  default     = ""
  description = "Exact verified GitHub OIDC sub claim, including immutable IDs if applicable."
}
