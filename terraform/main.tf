# Raw zone of a data lake on AWS, written the way a regulated organisation would expect:
# encrypted with a customer-managed key, versioned, never public, TLS only,
# and an ingestion role that can write to raw/ and nothing else.
# Practice only: run `terraform init` and `terraform validate`; do not apply to a real account.

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

variable "region" {
  type    = string
  default = "ap-southeast-2"
}

variable "environment" {
  type    = string
  default = "dev"
}

locals {
  bucket_name = "dpp-lake-${var.environment}"
  tags = {
    environment = var.environment
    owner       = "data-platform"
    data_class  = "confidential"
  }
}

resource "aws_kms_key" "lake" {
  description         = "Encrypts the ${var.environment} data lake"
  enable_key_rotation = true
  tags                = local.tags
}

resource "aws_s3_bucket" "lake" {
  bucket = local.bucket_name
  tags   = local.tags
}

resource "aws_s3_bucket_versioning" "lake" {
  bucket = aws_s3_bucket.lake.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "lake" {
  bucket = aws_s3_bucket.lake.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.lake.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "lake" {
  bucket                  = aws_s3_bucket.lake.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

data "aws_iam_policy_document" "tls_only" {
  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.lake.arn,
      "${aws_s3_bucket.lake.arn}/*",
    ]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "lake" {
  bucket = aws_s3_bucket.lake.id
  policy = data.aws_iam_policy_document.tls_only.json
}

# Least privilege: the ingestion job can only write under raw/ and use the lake key.
data "aws_iam_policy_document" "ingest_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ingest" {
  name               = "dpp-ingest-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.ingest_assume.json
  tags               = local.tags
}

data "aws_iam_policy_document" "ingest_write_raw" {
  statement {
    actions   = ["s3:PutObject", "s3:AbortMultipartUpload"]
    resources = ["${aws_s3_bucket.lake.arn}/raw/*"]
  }
  statement {
    actions   = ["kms:GenerateDataKey", "kms:Encrypt"]
    resources = [aws_kms_key.lake.arn]
  }
}

resource "aws_iam_role_policy" "ingest_write_raw" {
  name   = "write-raw-only"
  role   = aws_iam_role.ingest.id
  policy = data.aws_iam_policy_document.ingest_write_raw.json
}

output "lake_bucket" {
  value = aws_s3_bucket.lake.bucket
}
