resource "aws_kms_alias" "audit_trail_key_alias" {
  name          = "alias/${local.env_prefix.value}-audit-bucket-key"
  target_key_id = "${aws_kms_key.audit_trail_key.key_id}"
}

resource "aws_kms_key" "audit_trail_key" {
  description = "${local.env_prefix.value}-audit bucket key"

  deletion_window_in_days = 7
  tags = {
  }
}
