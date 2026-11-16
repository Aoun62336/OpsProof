# Pre-provisioned security groups make the private ALB reachable exclusively
# from the API Gateway VPC Link (and from no arbitrary public source).
resource "aws_security_group" "edge_vpc_link" {
  count       = var.enable_paid_resources ? 1 : 0
  name_prefix = "${local.name}-edge-vpclink-"
  description = "VPC Link to internal read-only ALB only"
  vpc_id      = aws_vpc.main[0].id
  lifecycle { create_before_destroy = true }
}
resource "aws_security_group" "edge_alb" {
  count       = var.enable_paid_resources ? 1 : 0
  name_prefix = "${local.name}-edge-alb-"
  description = "Internal ALB ingress only from OpsProof API Gateway VPC Link"
  vpc_id      = aws_vpc.main[0].id
  lifecycle { create_before_destroy = true }
}
resource "aws_vpc_security_group_ingress_rule" "edge_alb_from_vpc_link" {
  count                        = var.enable_paid_resources ? 1 : 0
  security_group_id            = aws_security_group.edge_alb[0].id
  referenced_security_group_id = aws_security_group.edge_vpc_link[0].id
  ip_protocol                  = "tcp"
  from_port                    = 80
  to_port                      = 80
}
resource "aws_vpc_security_group_egress_rule" "vpc_link_to_alb" {
  count                        = var.enable_paid_resources ? 1 : 0
  security_group_id            = aws_security_group.edge_vpc_link[0].id
  referenced_security_group_id = aws_security_group.edge_alb[0].id
  ip_protocol                  = "tcp"
  from_port                    = 80
  to_port                      = 80
}
resource "aws_vpc_security_group_egress_rule" "edge_alb_to_pods" {
  count             = var.enable_paid_resources ? 1 : 0
  security_group_id = aws_security_group.edge_alb[0].id
  cidr_ipv4         = aws_vpc.main[0].cidr_block
  ip_protocol       = "tcp"
  from_port         = 8080
  to_port           = 8080
}
