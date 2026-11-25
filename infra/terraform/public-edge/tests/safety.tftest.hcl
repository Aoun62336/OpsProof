# Every test uses a mocked AWS provider. No AWS endpoint or credentials are used.
mock_provider "aws" {
  mock_data "aws_caller_identity" {
    defaults = { account_id = "123456789012" }
  }
}

variables {
  expected_account_id        = "123456789012"
  approval_reference         = "OFFLINE_FIXTURE_ONLY"
  approval_acknowledgement   = "I_APPROVE_TEMPORARY_OPSPROOF_AWS_CHARGES"
  internal_alb_listener_arn  = "arn:aws:elasticloadbalancing:ap-south-1:123456789012:listener/app/test/1234567890123456/1234567890123456"
  private_subnet_ids         = ["subnet-12345678", "subnet-87654321"]
  vpc_link_security_group_id = "sg-12345678"
}
run "disabled_edge" {
  command = plan
  assert {
    condition     = length(aws_apigatewayv2_api.edge) == 0
    error_message = "Public ingress must default disabled."
  }
}
run "read_only_routes" {
  command = plan
  variables { enable_paid_resources = true }
  assert {
    condition     = aws_apigatewayv2_route.index[0].route_key == "GET /" && aws_apigatewayv2_route.health[0].route_key == "GET /healthz"
    error_message = "Only the two reviewed GET routes may be public."
  }
  assert {
    condition     = aws_apigatewayv2_integration.edge[0].connection_type == "VPC_LINK" && aws_apigatewayv2_integration.edge[0].integration_method == "GET"
    error_message = "Public ingress must use the private VPC link."
  }
}
run "reject_foreign_listener" {
  command = plan
  variables {
    enable_paid_resources     = true
    internal_alb_listener_arn = "arn:aws:elasticloadbalancing:ap-south-1:000000000000:listener/app/test/1234567890123456/1234567890123456"
  }
  expect_failures = [terraform_data.gate]
}
