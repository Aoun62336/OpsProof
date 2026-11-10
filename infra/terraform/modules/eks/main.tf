resource "aws_iam_role" "control_plane" {
  name = "${var.name}-control-plane"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "eks.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}
resource "aws_iam_role_policy_attachment" "cluster" {
  role       = aws_iam_role.control_plane.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}
# Explicit lifecycle for EKS control-plane log data; do not retain unbounded
# CloudWatch logs after the temporary verification environment is destroyed.
resource "aws_cloudwatch_log_group" "cluster" {
  name              = "/aws/eks/${var.name}/cluster"
  retention_in_days = 1
}

resource "aws_eks_cluster" "this" {
  name     = var.name
  role_arn = aws_iam_role.control_plane.arn
  version  = var.kubernetes_version
  vpc_config {
    subnet_ids              = var.subnet_ids
    endpoint_private_access = true
    endpoint_public_access  = true
    public_access_cidrs     = [var.allowed_cidr]
  }
  access_config {
    authentication_mode                         = "API"
    bootstrap_cluster_creator_admin_permissions = false
  }
  enabled_cluster_log_types = ["api", "audit", "authenticator"]
  depends_on                = [aws_iam_role_policy_attachment.cluster, aws_cloudwatch_log_group.cluster]
}
resource "aws_eks_access_entry" "operator" {
  cluster_name  = aws_eks_cluster.this.name
  principal_arn = var.operator_role_arn
  type          = "STANDARD"
}
resource "aws_eks_access_policy_association" "operator" {
  cluster_name  = aws_eks_cluster.this.name
  principal_arn = aws_eks_access_entry.operator.principal_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
  access_scope { type = "cluster" }
}
resource "aws_eks_node_group" "single" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "${var.name}-single"
  node_role_arn   = var.node_role_arn
  subnet_ids      = var.subnet_ids
  capacity_type   = "ON_DEMAND"
  ami_type        = "AL2023_x86_64_STANDARD"
  instance_types  = [var.node_instance_type]
  disk_size       = 30
  scaling_config {
    desired_size = 1
    min_size     = 1
    max_size     = 1
  }
  update_config {
    max_unavailable = 1
  }
  labels     = { "opsproof.io/environment" = "temporary-verification" }
  depends_on = [aws_eks_access_policy_association.operator]
}
resource "aws_eks_addon" "pod_identity_agent" {
  cluster_name = aws_eks_cluster.this.name
  addon_name   = "eks-pod-identity-agent"
  depends_on   = [aws_eks_node_group.single]
}
resource "aws_eks_addon" "vpc_cni" {
  cluster_name = aws_eks_cluster.this.name
  addon_name   = "vpc-cni"
  depends_on   = [aws_eks_node_group.single]
}
resource "aws_eks_addon" "coredns" {
  cluster_name = aws_eks_cluster.this.name
  addon_name   = "coredns"
  depends_on   = [aws_eks_node_group.single]
}
resource "aws_eks_addon" "kube_proxy" {
  cluster_name = aws_eks_cluster.this.name
  addon_name   = "kube-proxy"
  depends_on   = [aws_eks_node_group.single]
}
resource "aws_eks_pod_identity_association" "ebs_csi" {
  cluster_name    = aws_eks_cluster.this.name
  namespace       = "kube-system"
  service_account = "ebs-csi-controller-sa"
  role_arn        = var.ebs_role_arn
  depends_on      = [aws_eks_addon.pod_identity_agent]
}
resource "aws_eks_addon" "ebs_csi" {
  cluster_name = aws_eks_cluster.this.name
  addon_name   = "aws-ebs-csi-driver"
  depends_on   = [aws_eks_pod_identity_association.ebs_csi, aws_eks_node_group.single]
}
