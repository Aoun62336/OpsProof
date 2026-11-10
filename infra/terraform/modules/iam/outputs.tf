output "node_role_arn" { value = aws_iam_role.node.arn }
output "ebs_role_arn" { value = aws_iam_role.ebs.arn }
output "node_policy_attachment_ids" { value = [for a in aws_iam_role_policy_attachment.node : a.id] }
output "ebs_attachment_id" { value = aws_iam_role_policy_attachment.ebs.id }
