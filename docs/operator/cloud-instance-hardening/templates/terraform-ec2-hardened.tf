# AWS IMDSv2 Enforcement — Terraform Template

## Instance-Level
```hcl
resource "aws_instance" "hardened" {
  ami           = data.aws_ami.amazon_linux_2023.id
  instance_type = "t3.medium"
  
  metadata_options {
    http_tokens                 = "required"
    http_endpoint               = "enabled"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "disabled"
  }
  
  # ... rest of config
}
```

## Launch Template (Recommended for ASG)
```hcl
resource "aws_launch_template" "hardened" {
  name_prefix   = "hardened-"
  image_id      = data.aws_ami.amazon_linux_2023.id
  instance_type = "t3.medium"
  
  metadata_options {
    http_tokens                 = "required"
    http_endpoint               = "enabled"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "disabled"
  }
  
  # ... rest of config
}
```

## Auto Scaling Group with Hardened Template
```hcl
resource "aws_autoscaling_group" "hardened" {
  name                = "hardened-asg"
  launch_template {
    id      = aws_launch_template.hardened.id
    version = "$Latest"
  }
  min_size         = 2
  max_size         = 10
  desired_capacity = 3
  vpc_zone_identifier = var.private_subnet_ids
}
```

## Module Pattern (Reusable)
```hcl
# modules/ec2-hardened/main.tf
variable "instance_type" { type = string }
variable "ami_id"        { type = string }
variable "subnet_id"     { type = string }
variable "sg_ids"        { type = list(string) }

resource "aws_instance" "this" {
  instance_type = var.instance_type
  ami           = var.ami_id
  subnet_id     = var.subnet_id
  vpc_security_group_ids = var.sg_ids
  
  metadata_options {
    http_tokens                 = "required"
    http_endpoint               = "enabled"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "disabled"
  }
  
  tags = merge(var.tags, {
    Name = var.name
    Hardened = "true"
  })
}
```

## Usage
```hcl
module "app_server" {
  source        = "./modules/ec2-hardened"
  instance_type = "t3.medium"
  ami_id        = data.aws_ami.amazon_linux_2023.id
  subnet_id     = var.private_subnet_ids[0]
  sg_ids        = [aws_security_group.app.id]
  name          = "app-server"
  tags          = var.common_tags
}
```