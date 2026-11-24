terraform {
  required_version = ">= 1.10, < 2.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "= 5.100.0" }
  }
}
provider "aws" {
  region              = "us-east-1"
  allowed_account_ids = ["646941583111"]
  default_tags { tags = { Project = "citas-image-builder", ManagedBy = "Terraform" } }
}
variable "public_key" { type = string }
data "aws_vpc" "existing" {
  filter {
    name   = "tag:Name"
    values = ["citas-api"]
  }
}
data "aws_subnet" "existing" {
  filter {
    name   = "tag:Name"
    values = ["citas-api-public-1"]
  }
  vpc_id = data.aws_vpc.existing.id
}
data "aws_ssm_parameter" "ubuntu" {
  name = "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id"
}
resource "aws_key_pair" "builder" {
  key_name   = "maiag19-builder"
  public_key = var.public_key
}
resource "aws_security_group" "builder" {
  name_prefix = "citas-image-builder-"
  description = "Builder sin puertos entrantes; acceso por SSM"
  vpc_id      = data.aws_vpc.existing.id
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "aws_iam_role" "builder" {
  name               = "citas-image-builder"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "ec2.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}
resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.builder.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}
resource "aws_iam_role_policy" "artifacts" {
  role = aws_iam_role.builder.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["s3:GetObject"], Resource = ["arn:aws:s3:::citas-api-models-646941583111-us-east-1/releases/ms-scibert-b8ee47317c29afbc/*"] },
    # Descargas públicas solicitadas: escritura solo en el prefijo models del sitio.
    { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject", "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts"], Resource = "arn:aws:s3:::citas-api-web-646941583111-us-east-1/models/*" },
    { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:GetObjectTagging", "s3:PutObjectTagging", "s3:DeleteObjectTagging", "s3:GetObjectVersion", "s3:DeleteObjectVersion", "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts"], Resource = "arn:aws:s3:::citas-api-models-646941583111-us-east-1/experiments/t04-ms-serverless/b75e3075c4bf630d1b5aaf9c0ce7a2e43265446231ed550869e6df38b35def7f/model.tar.gz" },
    { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"], Resource = ["arn:aws:s3:::citas-api-models-646941583111-us-east-1/terraform/t04-ms-artifact/terraform.tfstate", "arn:aws:s3:::citas-api-models-646941583111-us-east-1/terraform/t04-ms-artifact/terraform.tfstate.tflock"] },
    { Effect = "Allow", Action = ["s3:GetBucketLocation", "s3:ListBucket"], Resource = "arn:aws:s3:::citas-api-models-646941583111-us-east-1" },
    { Effect = "Allow", Action = ["s3:ListBucketVersions"], Resource = "arn:aws:s3:::citas-api-models-646941583111-us-east-1", Condition = { StringLike = { "s3:prefix" = ["experiments/t04-ms-serverless/b75e3075c4bf630d1b5aaf9c0ce7a2e43265446231ed550869e6df38b35def7f/model.tar.gz", "terraform/t04-ms-artifact/terraform.tfstate*", "env:/"] } } },
    { Effect = "Allow", Action = ["ecr:GetAuthorizationToken"], Resource = "*" },
    { Effect = "Allow", Action = ["ecr:BatchCheckLayerAvailability", "ecr:InitiateLayerUpload", "ecr:UploadLayerPart", "ecr:CompleteLayerUpload", "ecr:PutImage", "ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:DescribeImages"], Resource = ["arn:aws:ecr:us-east-1:646941583111:repository/citas-ms-serverless-t04", "arn:aws:ecr:us-east-1:646941583111:repository/citas-api"] }
  ] })
}
resource "aws_iam_instance_profile" "builder" {
  name = "citas-image-builder"
  role = aws_iam_role.builder.name
}
resource "aws_instance" "builder" {
  lifecycle {
    prevent_destroy = true
    # La IP efímera desaparece al apagar; eso no debe recrear el disco/modelos.
    ignore_changes = [associate_public_ip_address]
  }
  ami                         = nonsensitive(data.aws_ssm_parameter.ubuntu.value)
  instance_type               = "t3.large"
  subnet_id                   = data.aws_subnet.existing.id
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.builder.id]
  key_name                    = aws_key_pair.builder.key_name
  iam_instance_profile        = aws_iam_instance_profile.builder.name
  metadata_options { http_tokens = "required" }
  root_block_device {
    volume_size           = 60
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = true
  }
  user_data                   = file("${path.module}/bootstrap.sh")
  user_data_replace_on_change = true
  tags                        = { Name = "citas-image-builder" }
}
output "instance_id" { value = aws_instance.builder.id }
output "public_ip" { value = aws_instance.builder.public_ip }

variable "builder_power_state" {
  type    = string
  default = "stopped"
  validation {
    condition     = contains(["running", "stopped"], var.builder_power_state)
    error_message = "El constructor solo admite running o stopped."
  }
}
resource "aws_ec2_instance_state" "builder" {
  instance_id = aws_instance.builder.id
  state       = var.builder_power_state
}
