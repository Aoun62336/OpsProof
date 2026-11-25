# Domain-free public ingress: API Gateway's managed execute-api HTTPS hostname.
# API Gateway HTTP API enforces TLS >= 1.2 for viewers without buying a domain.
# The VPC Link forwards only GET / and GET /healthz to the PRIVATE ALB listener
# over private HTTP. No operator API, tokens, credentials, or user data allowed.
variable "enable_paid_resources" {
  type    = bool
  default = false
}
variable "expected_account_id" {
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
variable "internal_alb_listener_arn" {
  type    = string
  default = ""
}
variable "private_subnet_ids" {
  type    = list(string)
  default = []
}
variable "vpc_link_security_group_id" {
  type    = string
  default = ""
}

data "aws_caller_identity" "current" { count = var.enable_paid_resources ? 1 : 0 }
resource "terraform_data" "gate" {
  count = var.enable_paid_resources ? 1 : 0
  input = var.approval_reference
  lifecycle {
    precondition {
      condition = (
        var.approval_acknowledgement == "I_APPROVE_TEMPORARY_OPSPROOF_AWS_CHARGES" &&
        var.expected_account_id == data.aws_caller_identity.current[0].account_id &&
        length(var.approval_reference) >= 12 &&
        can(regex("^arn:aws:elasticloadbalancing:ap-south-1:${var.expected_account_id}:listener/app/", var.internal_alb_listener_arn)) &&
        length(var.private_subnet_ids) == 2 &&
        can(regex("^sg-[a-f0-9]{8,17}$", var.vpc_link_security_group_id))
      )
      error_message = "EDGE GATE BLOCKED: verified AWS account, private subnets, VPC Link security group, internal ALB listener and human approval required."
    }
  }
}
resource "aws_apigatewayv2_vpc_link" "edge" {
  count              = var.enable_paid_resources ? 1 : 0
  name               = "opsproof-cloud-private-vpc-link"
  subnet_ids         = var.private_subnet_ids
  security_group_ids = [var.vpc_link_security_group_id]
  depends_on         = [terraform_data.gate]
}
resource "aws_apigatewayv2_api" "edge" {
  count                        = var.enable_paid_resources ? 1 : 0
  name                         = "opsproof-cloud-read-only-edge"
  protocol_type                = "HTTP"
  disable_execute_api_endpoint = false
  description                  = "Public TLS 1.2 read-only ingress proof; no OpsProof control-plane API exposed"
}
resource "aws_apigatewayv2_integration" "edge" {
  count                  = var.enable_paid_resources ? 1 : 0
  api_id                 = aws_apigatewayv2_api.edge[0].id
  integration_type       = "HTTP_PROXY"
  integration_method     = "GET"
  integration_uri        = var.internal_alb_listener_arn
  connection_type        = "VPC_LINK"
  connection_id          = aws_apigatewayv2_vpc_link.edge[0].id
  payload_format_version = "1.0"
  request_parameters     = { "overwrite:path" = "$request.path" }
}
resource "aws_apigatewayv2_route" "index" {
  count     = var.enable_paid_resources ? 1 : 0
  api_id    = aws_apigatewayv2_api.edge[0].id
  route_key = "GET /"
  target    = "integrations/${aws_apigatewayv2_integration.edge[0].id}"
}
resource "aws_apigatewayv2_route" "health" {
  count     = var.enable_paid_resources ? 1 : 0
  api_id    = aws_apigatewayv2_api.edge[0].id
  route_key = "GET /healthz"
  target    = "integrations/${aws_apigatewayv2_integration.edge[0].id}"
}
resource "aws_apigatewayv2_stage" "default" {
  count       = var.enable_paid_resources ? 1 : 0
  api_id      = aws_apigatewayv2_api.edge[0].id
  name        = "$default"
  auto_deploy = true
  default_route_settings {
    throttling_burst_limit = 10
    throttling_rate_limit  = 5
  }
  depends_on = [aws_apigatewayv2_route.index, aws_apigatewayv2_route.health]
}
output "public_https_url" {
  value = var.enable_paid_resources ? aws_apigatewayv2_api.edge[0].api_endpoint : null
}
output "http_api_id" {
  value = var.enable_paid_resources ? aws_apigatewayv2_api.edge[0].id : null
}
output "viewer_tls_minimum" { value = "TLSv1.2 (API Gateway HTTP API managed policy)" }
output "private_alb_origin_tls" { value = false }
