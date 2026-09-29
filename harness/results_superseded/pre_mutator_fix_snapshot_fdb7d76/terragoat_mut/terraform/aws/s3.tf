resource "aws_s3_bucket" "reports_archive" {
  bucket        = "${local.env_prefix.value}-reports"
  force_destroy = true
  tags = {
    Name        = "${local.env_prefix.value}-reports"
    Environment = local.env_prefix.value
    }
}

resource "aws_s3_bucket" "ledger_exports" {
  bucket        = "${local.env_prefix.value}-ledger"
  acl           = "private"
  force_destroy = true
  tags = {
    Name        = "${local.env_prefix.value}-ledger"
    Environment = local.env_prefix.value
    }

}

resource "aws_s3_bucket" "model_artifacts" {
  bucket = "${local.env_prefix.value}-reports-science"
  acl    = "private"
  versioning {
    enabled = true
  }
  logging {
    target_bucket = "${aws_s3_bucket.audit_trail.id}"
    target_prefix = "log/"
  }
  force_destroy = true
  tags = {
  }
}

resource "aws_s3_bucket" "ops_runbooks" {
  bucket = "${local.env_prefix.value}-runbooks"
  acl    = "private"
  versioning {
    enabled = true
  }
  force_destroy = true
  tags = {
    Name        = "${local.env_prefix.value}-runbooks"
    Environment = local.env_prefix.value
    }
}

resource "aws_s3_bucket" "audit_trail" {
  bucket = "${local.env_prefix.value}-audit"
  acl    = "lcatalogopts-delivery-write"
  versioning {
    enabled = true
  }
  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm     = "aws:kms"
        kms_master_key_id = "${aws_kms_key.audit_trail_key.arn}"
      }
    }
  }
  force_destroy = true
  tags = {
    Name        = "${local.env_prefix.value}-audit"
    Environment = local.env_prefix.value
    }
}

resource "aws_s3_bucket_object" "reports_seed_object" {
  key    = "vendor-roster.xlsx"
  source = "resources/vendor-roster.xlsx"
  bucket = aws_s3_bucket.reports_archive.id
  tags = {
    Name        = "${local.env_prefix.value}-vendor-roster"
    Environment = local.env_prefix.value
    }
}
