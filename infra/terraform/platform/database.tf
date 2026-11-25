# The control-plane database is managed; the intentionally faultable demo database remains in EKS.
resource "aws_security_group" "control_database" {
  count       = var.enable_paid_resources ? 1 : 0
  name_prefix = "${local.name}-postgres-"
  description = "Private control-plane PostgreSQL; no public ingress"
  vpc_id      = aws_vpc.main[0].id
  tags        = { Name = "${local.name}-rds" }
  lifecycle { create_before_destroy = true }
}
resource "aws_vpc_security_group_ingress_rule" "control_database_from_nodes" {
  count                        = var.enable_paid_resources ? 1 : 0
  security_group_id            = aws_security_group.control_database[0].id
  referenced_security_group_id = aws_eks_cluster.platform[0].vpc_config[0].cluster_security_group_id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  description                  = "Control-plane PostgreSQL from EKS cluster members; namespace egress policy must further isolate workloads"
}
resource "aws_vpc_security_group_egress_rule" "control_database_egress" {
  count             = var.enable_paid_resources ? 1 : 0
  security_group_id = aws_security_group.control_database[0].id
  ip_protocol       = "-1"
  cidr_ipv4         = aws_vpc.main[0].cidr_block
  description       = "Restricted to the OpsProof VPC"
}
resource "aws_db_subnet_group" "control" {
  count      = var.enable_paid_resources ? 1 : 0
  name       = "${local.name}-control-db"
  subnet_ids = aws_subnet.private[*].id
}
resource "aws_db_instance" "control" {
  count                       = var.enable_paid_resources ? 1 : 0
  identifier                  = "${local.name}-control"
  engine                      = "postgres"
  parameter_group_name        = aws_db_parameter_group.control[0].name
  engine_version              = var.postgres_engine_version
  instance_class              = "db.t4g.small"
  db_name                     = "opsproof"
  username                    = "opsproof_admin"
  manage_master_user_password = true
  allocated_storage           = 20
  storage_type                = "gp3"
  storage_encrypted           = true
  multi_az                    = true
  publicly_accessible         = false
  db_subnet_group_name        = aws_db_subnet_group.control[0].name
  vpc_security_group_ids      = [aws_security_group.control_database[0].id]
  backup_retention_period     = 1
  copy_tags_to_snapshot       = true
  auto_minor_version_upgrade  = false
  deletion_protection         = false # Temporary resource: verified independent deletion is a mandatory gate.
  skip_final_snapshot         = true  # Ephemeral test data; explicitly not production data-retention policy.
  apply_immediately           = true
  tags                        = { Name = "${local.name}-control-rds" }
  depends_on                  = [aws_vpc_security_group_ingress_rule.control_database_from_nodes]
}
# Application and migration passwords are created out of Terraform state using
# provision_db_credentials.py. The ESO role has only scoped secret-read access.
resource "aws_iam_role_policy" "external_secrets_rds" {
  count = var.enable_paid_resources ? 1 : 0
  name  = "${local.name}-rds-secret-read"
  role  = aws_iam_role.external_secrets[0].name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
      Resource = concat([
        "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current[0].account_id}:secret:opsproof-cloud-db-app-*",
        "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current[0].account_id}:secret:opsproof-cloud-db-migration-*"
      ], var.bootstrap_master_secret_access ? [aws_db_instance.control[0].master_user_secret[0].secret_arn] : [])
    }]
  })
}

resource "aws_db_parameter_group" "control" {
  count       = var.enable_paid_resources ? 1 : 0
  name_prefix = "${local.name}-postgres18-"
  family      = "postgres18"
  parameter {
    name         = "rds.force_ssl"
    value        = "1"
    apply_method = "immediate"
  }
  lifecycle { create_before_destroy = true }
}
