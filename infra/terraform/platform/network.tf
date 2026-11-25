# One VPC, two AZs, private nodes, and exactly one NAT. NAT is an explicit single-AZ failure dependency.
resource "aws_vpc" "main" {
  count                = var.enable_paid_resources ? 1 : 0
  cidr_block           = "10.72.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "${local.name}-vpc" }
  depends_on           = [terraform_data.spend_gate]
}
resource "aws_internet_gateway" "main" {
  count  = var.enable_paid_resources ? 1 : 0
  vpc_id = aws_vpc.main[0].id
  tags   = { Name = "${local.name}-igw" }
}
resource "aws_subnet" "public" {
  count                   = var.enable_paid_resources ? 2 : 0
  vpc_id                  = aws_vpc.main[0].id
  availability_zone       = var.availability_zones[count.index]
  cidr_block              = cidrsubnet(aws_vpc.main[0].cidr_block, 8, count.index + 10)
  map_public_ip_on_launch = false
  tags = {
    Name                                  = "${local.name}-public-${count.index + 1}"
    "kubernetes.io/role/elb"              = "1"
    "kubernetes.io/cluster/${local.name}" = "shared"
  }
}
resource "aws_subnet" "private" {
  count                   = var.enable_paid_resources ? 2 : 0
  vpc_id                  = aws_vpc.main[0].id
  availability_zone       = var.availability_zones[count.index]
  cidr_block              = cidrsubnet(aws_vpc.main[0].cidr_block, 8, count.index + 20)
  map_public_ip_on_launch = false
  tags = {
    Name                                  = "${local.name}-private-${count.index + 1}"
    "kubernetes.io/role/internal-elb"     = "1"
    "kubernetes.io/cluster/${local.name}" = "shared"
  }
}
resource "aws_route_table" "public" {
  count  = var.enable_paid_resources ? 1 : 0
  vpc_id = aws_vpc.main[0].id
  tags   = { Name = "${local.name}-public-rt" }
}
resource "aws_route" "public_internet" {
  count                  = var.enable_paid_resources ? 1 : 0
  route_table_id         = aws_route_table.public[0].id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.main[0].id
}
resource "aws_route_table_association" "public" {
  count          = var.enable_paid_resources ? 2 : 0
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public[0].id
}
resource "aws_eip" "nat" {
  count      = var.enable_paid_resources ? 1 : 0
  domain     = "vpc"
  tags       = { Name = "${local.name}-nat-eip" }
  depends_on = [aws_internet_gateway.main]
}
resource "aws_nat_gateway" "single" {
  count         = var.enable_paid_resources ? 1 : 0
  subnet_id     = aws_subnet.public[0].id
  allocation_id = aws_eip.nat[0].id
  tags          = { Name = "${local.name}-nat-single-az" }
  depends_on    = [aws_route_table_association.public]
}
resource "aws_route_table" "private" {
  count  = var.enable_paid_resources ? 2 : 0
  vpc_id = aws_vpc.main[0].id
  tags   = { Name = "${local.name}-private-rt-${count.index + 1}" }
}
resource "aws_route" "private_egress" {
  count                  = var.enable_paid_resources ? 2 : 0
  route_table_id         = aws_route_table.private[count.index].id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.single[0].id
}
resource "aws_route_table_association" "private" {
  count          = var.enable_paid_resources ? 2 : 0
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}
resource "aws_vpc_endpoint" "s3" {
  count             = var.enable_paid_resources ? 1 : 0
  vpc_id            = aws_vpc.main[0].id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [for route in aws_route_table.private : route.id]
  tags              = { Name = "${local.name}-s3-gateway" }
}
