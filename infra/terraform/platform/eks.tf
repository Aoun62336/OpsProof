resource "aws_cloudwatch_log_group" "eks" {
  count             = var.enable_paid_resources ? 1 : 0
  name              = "/aws/eks/${local.name}/cluster"
  retention_in_days = 1
}
resource "aws_eks_cluster" "platform" {
  count    = var.enable_paid_resources ? 1 : 0
  name     = local.name
  role_arn = aws_iam_role.eks_control[0].arn
  version  = var.kubernetes_version
  vpc_config {
    subnet_ids              = concat(aws_subnet.public[*].id, aws_subnet.private[*].id)
    endpoint_public_access  = true
    endpoint_private_access = true
    public_access_cidrs     = [var.operator_public_cidr]
  }
  kubernetes_network_config {
    ip_family         = "ipv4"
    service_ipv4_cidr = "172.20.0.0/16"
  }
  access_config {
    authentication_mode                         = "API"
    bootstrap_cluster_creator_admin_permissions = false
  }
  enabled_cluster_log_types = ["api", "audit", "authenticator"]
  depends_on                = [aws_iam_role_policy_attachment.eks_control, aws_cloudwatch_log_group.eks]
}
resource "aws_eks_access_entry" "operator" {
  count         = var.enable_paid_resources ? 1 : 0
  cluster_name  = aws_eks_cluster.platform[0].name
  principal_arn = var.operator_role_arn
  type          = "STANDARD"
}
resource "aws_eks_access_policy_association" "operator" {
  count         = var.enable_paid_resources ? 1 : 0
  cluster_name  = aws_eks_cluster.platform[0].name
  principal_arn = aws_eks_access_entry.operator[0].principal_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
  access_scope { type = "cluster" }
}
# Enforce one instance per AZ rather than hoping a multi-AZ nodegroup distributes evenly.
resource "aws_eks_node_group" "zone" {
  count           = var.enable_paid_resources ? 2 : 0
  cluster_name    = aws_eks_cluster.platform[0].name
  node_group_name = "${local.name}-az-${count.index + 1}"
  node_role_arn   = aws_iam_role.node[0].arn
  subnet_ids      = [aws_subnet.private[count.index].id]
  capacity_type   = "ON_DEMAND"
  ami_type        = "AL2023_x86_64_STANDARD"
  instance_types  = [var.node_instance_type]
  disk_size       = 30
  scaling_config {
    desired_size = 1
    min_size     = 1
    max_size     = 1
  }
  update_config { max_unavailable = 1 }
  labels = {
    "opsproof.io/profile"   = "temporary-verification"
    "opsproof.io/node-zone" = tostring(count.index + 1)
  }
  depends_on = [aws_eks_access_policy_association.operator, aws_iam_role_policy_attachment.node, aws_iam_role_policy_attachment.cni_bootstrap, aws_route.private_egress]
}
# The Pod Identity agent is required before the role associations can supply credentials.
resource "aws_eks_addon" "pod_identity" {
  count         = var.enable_paid_resources ? 1 : 0
  cluster_name  = aws_eks_cluster.platform[0].name
  addon_name    = "eks-pod-identity-agent"
  addon_version = lookup(var.addon_versions, "eks-pod-identity-agent", null)
  depends_on    = [aws_eks_node_group.zone]
}
resource "aws_eks_pod_identity_association" "cni" {
  count           = var.enable_paid_resources ? 1 : 0
  cluster_name    = aws_eks_cluster.platform[0].name
  namespace       = "kube-system"
  service_account = "aws-node"
  role_arn        = aws_iam_role.cni[0].arn
  depends_on      = [aws_eks_addon.pod_identity, aws_iam_role_policy_attachment.cni]
}
resource "aws_eks_pod_identity_association" "ebs" {
  count           = var.enable_paid_resources ? 1 : 0
  cluster_name    = aws_eks_cluster.platform[0].name
  namespace       = "kube-system"
  service_account = "ebs-csi-controller-sa"
  role_arn        = aws_iam_role.ebs[0].arn
  depends_on      = [aws_eks_addon.pod_identity, aws_iam_role_policy_attachment.ebs]
}
resource "aws_eks_pod_identity_association" "alb" {
  count           = var.enable_paid_resources ? 1 : 0
  cluster_name    = aws_eks_cluster.platform[0].name
  namespace       = "kube-system"
  service_account = "aws-load-balancer-controller"
  role_arn        = aws_iam_role.alb_controller[0].arn
  depends_on      = [aws_eks_addon.pod_identity, aws_iam_role_policy_attachment.alb_controller]
}
resource "aws_eks_pod_identity_association" "external_secrets" {
  count           = var.enable_paid_resources ? 1 : 0
  cluster_name    = aws_eks_cluster.platform[0].name
  namespace       = "external-secrets"
  service_account = "external-secrets"
  role_arn        = aws_iam_role.external_secrets[0].arn
  depends_on      = [aws_eks_addon.pod_identity]
}
resource "aws_eks_addon" "vpc_cni" {
  count                       = var.enable_paid_resources ? 1 : 0
  cluster_name                = aws_eks_cluster.platform[0].name
  addon_name                  = "vpc-cni"
  addon_version               = lookup(var.addon_versions, "vpc-cni", null)
  configuration_values        = jsonencode({ enableNetworkPolicy = "true" })
  resolve_conflicts_on_create = "OVERWRITE"
  depends_on                  = [aws_eks_pod_identity_association.cni]
}
resource "aws_eks_addon" "kube_proxy" {
  count                       = var.enable_paid_resources ? 1 : 0
  cluster_name                = aws_eks_cluster.platform[0].name
  addon_name                  = "kube-proxy"
  addon_version               = lookup(var.addon_versions, "kube-proxy", null)
  resolve_conflicts_on_create = "OVERWRITE"
  depends_on                  = [aws_eks_node_group.zone]
}
resource "aws_eks_addon" "coredns" {
  count                       = var.enable_paid_resources ? 1 : 0
  cluster_name                = aws_eks_cluster.platform[0].name
  addon_name                  = "coredns"
  addon_version               = lookup(var.addon_versions, "coredns", null)
  resolve_conflicts_on_create = "OVERWRITE"
  depends_on                  = [aws_eks_node_group.zone]
}
resource "aws_eks_addon" "ebs_csi" {
  count         = var.enable_paid_resources ? 1 : 0
  cluster_name  = aws_eks_cluster.platform[0].name
  addon_name    = "aws-ebs-csi-driver"
  addon_version = lookup(var.addon_versions, "aws-ebs-csi-driver", null)
  depends_on    = [aws_eks_pod_identity_association.ebs]
}

resource "aws_eks_addon" "metrics_server" {
  count         = var.enable_paid_resources ? 1 : 0
  cluster_name  = aws_eks_cluster.platform[0].name
  addon_name    = "metrics-server"
  addon_version = lookup(var.addon_versions, "metrics-server", null)
  depends_on    = [aws_eks_node_group.zone]
}
