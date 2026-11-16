# Every test uses a mocked AWS provider. No AWS endpoint or credentials are used.
mock_provider "aws" {
  mock_data "aws_caller_identity" {
    defaults = { account_id = "123456789012" }
  }
}

run "disabled_graph" {
  command = plan
  variables { availability_zones = [] }
  assert {
    condition     = length(aws_vpc.main) == 0 && length(aws_eks_cluster.platform) == 0 && length(aws_db_instance.control) == 0
    error_message = "Default configuration must create no paid infrastructure."
  }
}
variables {
  expected_account_id        = "123456789012"
  approval_reference         = "OFFLINE_FIXTURE_ONLY"
  approval_acknowledgement   = "I_APPROVE_TEMPORARY_OPSPROOF_AWS_CHARGES"
  operator_role_arn          = "arn:aws:iam::123456789012:role/opsproof-test-operator"
  operator_public_cidr       = "203.0.113.5/32"
  availability_zones         = ["ap-south-1a", "ap-south-1b"]
  kubernetes_version         = "1.35"
  postgres_engine_version    = "18.6"
  maximum_approved_hours     = 2
  gross_budget_usd           = 15
  alb_controller_policy_file = "tests/fixtures/controller-policy.json"
  # Synthetic versions are test fixtures, never deployment selections.
  addon_versions = {
    eks-pod-identity-agent = "v1.0.0-eksbuild.1"
    vpc-cni                = "v1.0.0-eksbuild.1"
    kube-proxy             = "v1.0.0-eksbuild.1"
    coredns                = "v1.0.0-eksbuild.1"
    aws-ebs-csi-driver     = "v1.0.0-eksbuild.1"
    metrics-server         = "v1.0.0-eksbuild.1"
  }
}
run "enabled_topology" {
  command = plan
  variables { enable_paid_resources = true }
  assert {
    condition     = length(aws_eks_node_group.zone) == 2 && length(aws_nat_gateway.single) == 1
    error_message = "Require exactly two AZ-specific worker groups and one NAT."
  }
  assert {
    condition     = alltrue([for subnet in aws_subnet.private : !subnet.map_public_ip_on_launch]) && alltrue([for subnet in aws_subnet.public : !subnet.map_public_ip_on_launch])
    error_message = "Subnets must not assign public IPs automatically."
  }
  assert {
    condition     = aws_db_instance.control[0].multi_az && !aws_db_instance.control[0].publicly_accessible && aws_db_instance.control[0].storage_encrypted && aws_db_instance.control[0].engine_version == "18.6"
    error_message = "Managed control PostgreSQL must preserve the reviewed security/version contract."
  }
  assert {
    condition     = !aws_eks_cluster.platform[0].access_config[0].bootstrap_cluster_creator_admin_permissions && aws_eks_cluster.platform[0].vpc_config[0].public_access_cidrs == toset(["203.0.113.5/32"])
    error_message = "Cluster access must stay explicit and scoped to the operator."
  }
  assert {
    condition     = alltrue([for group in aws_eks_node_group.zone : length(group.subnet_ids) == 1 && group.scaling_config[0].desired_size == 1 && group.scaling_config[0].max_size == 1])
    error_message = "Worker groups must be one node in one private AZ subnet each."
  }
}
run "reject_account_mismatch" {
  command = plan
  variables { enable_paid_resources = true }
  override_data {
    target = data.aws_caller_identity.current
    values = { account_id = "000000000000" }
  }
  expect_failures = [terraform_data.spend_gate]
}
run "reject_missing_approval" {
  command = plan
  variables {
    enable_paid_resources    = true
    approval_acknowledgement = ""
  }
  expect_failures = [terraform_data.spend_gate]
}
run "reject_unpinned_addons" {
  command = plan
  variables {
    enable_paid_resources = true
    addon_versions        = {}
  }
  expect_failures = [terraform_data.spend_gate]
}
