output "paid_enabled" { value = var.enable_paid_resources }
output "region" { value = var.region }
output "cluster_name" { value = var.enable_paid_resources ? aws_eks_cluster.platform[0].name : null }
output "vpc_id" { value = var.enable_paid_resources ? aws_vpc.main[0].id : null }
output "private_subnet_ids" { value = aws_subnet.private[*].id }
output "node_groups" { value = aws_eks_node_group.zone[*].node_group_name }
output "control_db_endpoint" { value = var.enable_paid_resources ? aws_db_instance.control[0].address : null }
output "rds_master_secret_arn" { value = var.enable_paid_resources ? aws_db_instance.control[0].master_user_secret[0].secret_arn : null }
output "alb_controller_role_arn" { value = var.enable_paid_resources ? aws_iam_role.alb_controller[0].arn : null }
output "external_secrets_role_arn" { value = var.enable_paid_resources ? aws_iam_role.external_secrets[0].arn : null }
output "rds_is_multi_az" { value = var.enable_paid_resources ? aws_db_instance.control[0].multi_az : null }
output "nat_count" { value = length(aws_nat_gateway.single) }
output "edge_alb_security_group_id" { value = var.enable_paid_resources ? aws_security_group.edge_alb[0].id : null }
output "edge_vpc_link_security_group_id" { value = var.enable_paid_resources ? aws_security_group.edge_vpc_link[0].id : null }

output "cni_temporary_bootstrap_policy_attached" { value = var.enable_paid_resources && var.bootstrap_cni_node_policy }

output "private_subnet_cidrs" { value = aws_subnet.private[*].cidr_block }
output "cluster_endpoint" { value = var.enable_paid_resources ? aws_eks_cluster.platform[0].endpoint : null }
output "service_ipv4_cidr" { value = var.enable_paid_resources ? aws_eks_cluster.platform[0].kubernetes_network_config[0].service_ipv4_cidr : null }
