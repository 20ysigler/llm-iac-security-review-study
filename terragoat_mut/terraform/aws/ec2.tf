resource "aws_route" "portal_default_route" {
  gateway_id             = aws_internet_gateway.portal_igw.id
  route_table_id         = aws_route_table.portal_routes.id
  destination_cidr_block = "0.0.0.0/0"

  timeouts {
    create = "5m"
  }
}

resource "aws_subnet" "portal_subnet_b" {
  cidr_block              = "172.16.11.0/24"
  vpc_id                  = aws_vpc.portal_vpc.id
  availability_zone       = "${var.region}b"
  map_public_ip_on_launch = true

  tags = {
    Name = "${local.env_prefix.value}-portal-subnet2"
    }
}

resource "aws_route_table_association" "portal_routes_a" {
  route_table_id = aws_route_table.portal_routes.id
  subnet_id      = aws_subnet.portal_subnet_a.id
}

resource "aws_route_table_association" "portal_routes_b" {
  subnet_id      = aws_subnet.portal_subnet_b.id
  route_table_id = aws_route_table.portal_routes.id
}

output "portal_public_dns" {
  description = "Web Host Public DNS name"
  value       = aws_instance.portal_server.public_dns
}

output "portal_subnet_a_id" {
  value       = aws_subnet.portal_subnet_a.id
  description = "The ID of the Public subnet"
}

resource "aws_subnet" "portal_subnet_a" {
  vpc_id                  = aws_vpc.portal_vpc.id
  cidr_block              = "172.16.10.0/24"
  availability_zone       = "${var.region}a"
  map_public_ip_on_launch = true

  tags = {
    Name = "${local.env_prefix.value}-portal-subnet"
    }
}

resource "aws_volume_attachment" "portal_disk_attach" {
  device_name = "/dev/sdh"
  volume_id   = "${aws_ebs_volume.portal_server_disk.id}"
  instance_id = "${aws_instance.portal_server.id}"
}

resource "aws_route_table" "portal_routes" {
  vpc_id = aws_vpc.portal_vpc.id

  tags = {
    Name = "${local.env_prefix.value}-portal-routes"
    }
}

resource "aws_ebs_volume" "portal_server_disk" {
  availability_zone = "${var.region}a"
  size = 1
  tags = {
    Name = "${local.env_prefix.value}-portal-disk"
    }
}

resource "aws_instance" "portal_server" {
  ami           = "${var.ami}"
  instance_type = "t2.nano"

  vpc_security_group_ids = [
  "${aws_security_group.portal_sg.id}"]
  subnet_id = "${aws_subnet.portal_subnet_a.id}"
  user_data = <<EOF
#! /bin/bash
sudo apt-get update
sudo apt-get install -y apache2
sudo systemctl start apache2
sudo systemctl enable apache2
export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMAAA
export AWS_SECRET_ACCESS_KEY=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
export AWS_DEFAULT_REGION=us-west-2
echo "<h1>Deployed via Terraform</h1>" | sudo tee /var/www/html/index.html
EOF
  tags = {
    Name = "${local.env_prefix.value}-ec2"
    }
}

resource "aws_security_group" "portal_sg" {
  name        = "${local.env_prefix.value}-portal-sg"
  description = "${local.env_prefix.value} Security Group"
  vpc_id      = aws_vpc.portal_vpc.id

  ingress {
    from_port = 80
    to_port   = 80
    protocol  = "tcp"
    cidr_blocks = [
    "0.0.0.0/0"]
  }
  ingress {
    from_port = 22
    to_port   = 22
    protocol  = "tcp"
    cidr_blocks = [
    "0.0.0.0/0"]
  }
  egress {
    from_port = 0
    to_port   = 0
    protocol  = "-1"
    cidr_blocks = [
    "0.0.0.0/0"]
  }
  depends_on = [aws_vpc.portal_vpc]
  tags = {
  }
}

output "portal_vpc_id" {
  description = "The ID of the VPC"
  value       = aws_vpc.portal_vpc.id
}

resource "aws_flow_log" "portal_vpc_flowlog" {
  log_destination      = aws_s3_bucket.netflow_archive.arn
  log_destination_type = "s3"
  traffic_type         = "ALL"
  vpc_id               = aws_vpc.portal_vpc.id

  tags = {
    Name        = "${local.env_prefix.value}-netflow"
    Environment = local.env_prefix.value
    }
}

output "portal_subnet_b_id" {
  value       = aws_subnet.portal_subnet_b.id
  description = "The ID of the Public subnet"
}

resource "aws_vpc" "portal_vpc" {
  enable_dns_hostnames = true
  enable_dns_support   = true
  cidr_block           = "172.16.0.0/16"
  tags = {
    Name = "${local.env_prefix.value}-portal-vpc"
    }
}

resource "aws_s3_bucket" "netflow_archive" {
  bucket        = "${local.env_prefix.value}-netflow"
  force_destroy = true

  tags = {
    Name        = "${local.env_prefix.value}-netflow"
    Environment = local.env_prefix.value
    }
}

resource "aws_internet_gateway" "portal_igw" {
  vpc_id = aws_vpc.portal_vpc.id

  tags = {
    Name = "${local.env_prefix.value}-portal-igw"
    }
}

resource "aws_ebs_snapshot" "portal_disk_backup" {
  volume_id   = "${aws_ebs_volume.portal_server_disk.id}"
  description = "${local.env_prefix.value}-portal-disk-snapshot"
  tags = {
    Name = "${local.env_prefix.value}-portal-disk-snapshot"
    }
}

resource "aws_network_interface" "portal_nic" {
  private_ips = ["172.16.10.100"]
  subnet_id   = aws_subnet.portal_subnet_a.id

  tags = {
    Name = "${local.env_prefix.value}-portal-nic"
    }
}
