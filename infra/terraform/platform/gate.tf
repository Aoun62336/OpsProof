locals { name = "opsproof-cloud" }

data "aws_caller_identity" "current" { count = var.enable_paid_resources ? 1 : 0 }

resource "terraform_data" "spend_gate" {
  count = var.enable_paid_resources ? 1 : 0
  input = var.approval_reference
  lifecycle {
    precondition {
      condition = (
        var.approval_acknowledgement == "I_APPROVE_TEMPORARY_OPSPROOF_AWS_CHARGES" &&
        length(var.approval_reference) >= 12 &&
        data.aws_caller_identity.current[0].account_id == var.expected_account_id &&
        var.operator_role_arn != "" &&
        var.operator_public_cidr != "" &&
        var.kubernetes_version != "" &&
        length(var.availability_zones) == 2 &&
        var.maximum_approved_hours >= 1 && var.maximum_approved_hours <= 12 &&
        var.gross_budget_usd >= 1 && var.gross_budget_usd <= 40 &&
        can(regex("^arn:aws:iam::${var.expected_account_id}:role/[^*]+$", var.operator_role_arn)) &&
        var.postgres_engine_version != "" &&
        length(var.addon_versions) == 6 &&
        var.alb_controller_policy_file != "" &&
        fileexists(var.alb_controller_policy_file)
      )
      error_message = "PAID RESOURCE GATE BLOCKED: exact account/region/AZs, operator, approved budget and duration, actual LBC policy and explicit approval required."
    }
  }
}
