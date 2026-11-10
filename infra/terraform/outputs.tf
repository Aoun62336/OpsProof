output "cloud_resources_enabled" {
  description = "Whether the paid infrastructure gate was explicitly selected."
  value       = var.enable_paid_resources
}
output "cluster_name" {
  value = var.enable_paid_resources ? module.eks[0].cluster_name : null
}
output "cluster_arn" {
  value = var.enable_paid_resources ? module.eks[0].cluster_arn : null
}
output "vpc_id" {
  value = var.enable_paid_resources ? module.network[0].vpc_id : null
}
output "node_role_arn" {
  value = var.enable_paid_resources ? module.iam[0].node_role_arn : null
}
output "github_inspection_role_arn" {
  value = var.enable_paid_resources && var.enable_github_inspection_role ? aws_iam_role.github_inspect[0].arn : null
}
