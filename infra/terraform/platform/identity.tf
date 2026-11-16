# Identity boundaries: the worker IAM role cannot administer the cluster.
resource "aws_iam_role" "eks_control" {
  count = var.enable_paid_resources ? 1 : 0
  name  = "${local.name}-eks-control"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "eks.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}
resource "aws_iam_role_policy_attachment" "eks_control" {
  count      = var.enable_paid_resources ? 1 : 0
  role       = aws_iam_role.eks_control[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}
resource "aws_iam_role" "node" {
  count = var.enable_paid_resources ? 1 : 0
  name  = "${local.name}-worker"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ec2.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}
resource "aws_iam_role_policy_attachment" "node" {
  for_each = var.enable_paid_resources ? toset([
    "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPullOnly"
  ]) : toset([])
  role       = aws_iam_role.node[0].name
  policy_arn = each.value
}
locals {
  pod_identity_trust = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow", Principal = { Service = "pods.eks.amazonaws.com" }
      Action = ["sts:AssumeRole", "sts:TagSession"]
    }]
  })
}
resource "aws_iam_role" "cni" {
  count              = var.enable_paid_resources ? 1 : 0
  name               = "${local.name}-vpc-cni"
  assume_role_policy = local.pod_identity_trust
}
resource "aws_iam_role_policy_attachment" "cni" {
  count      = var.enable_paid_resources ? 1 : 0
  role       = aws_iam_role.cni[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
}
resource "aws_iam_role" "ebs" {
  count              = var.enable_paid_resources ? 1 : 0
  name               = "${local.name}-ebs-csi"
  assume_role_policy = local.pod_identity_trust
}
resource "aws_iam_role_policy_attachment" "ebs" {
  count      = var.enable_paid_resources ? 1 : 0
  role       = aws_iam_role.ebs[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
}
resource "aws_iam_role" "alb_controller" {
  count              = var.enable_paid_resources ? 1 : 0
  name               = "${local.name}-alb-controller"
  assume_role_policy = local.pod_identity_trust
}
# The exact upstream IAM policy must be reviewed and downloaded separately.
# It is purposefully not fabricated or committed here.
resource "aws_iam_policy" "alb_controller" {
  count  = var.enable_paid_resources ? 1 : 0
  name   = "${local.name}-alb-controller"
  policy = var.enable_paid_resources ? file(var.alb_controller_policy_file) : jsonencode({ Version = "2012-10-17", Statement = [] })
}
resource "aws_iam_role_policy_attachment" "alb_controller" {
  count      = var.enable_paid_resources ? 1 : 0
  role       = aws_iam_role.alb_controller[0].name
  policy_arn = aws_iam_policy.alb_controller[0].arn
}
resource "aws_iam_role" "external_secrets" {
  count              = var.enable_paid_resources ? 1 : 0
  name               = "${local.name}-external-secrets"
  assume_role_policy = local.pod_identity_trust
}

# Bootstrap necessity: aws-node needs CNI IAM before Pod Identity agent can run.
# Reapply with bootstrap_cni_node_policy=false after aws-node assumes the separate role.
resource "aws_iam_role_policy_attachment" "cni_bootstrap" {
  count      = var.enable_paid_resources && var.bootstrap_cni_node_policy ? 1 : 0
  role       = aws_iam_role.node[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
}
