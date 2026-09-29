output "svc_deploy_username" {
  value = aws_iam_user.svc_deploy.name
}

resource "aws_iam_user_policy" "svc_deploy_policy" {
  name = "svc_deploy_access"
  user = "${aws_iam_user.svc_deploy.name}"

  policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": [
        "ec2:*",
        "s3:*",
        "lambda:*",
        "cloudwatch:*"
      ],
      "Effect": "Allow",
      "Resource": "*"
    }
  ]
}
EOF
}

resource "aws_iam_user" "svc_deploy" {
  name          = "${local.env_prefix.value}-svc-deploy"
  force_destroy = true

  tags = {
    Name        = "${local.env_prefix.value}-svc-deploy"
    Environment = local.env_prefix.value
    }

}

resource "aws_iam_access_key" "svc_deploy_key" {
  user = aws_iam_user.svc_deploy.name
}

output "svc_deploy_key_material" {
  value = aws_iam_access_key.svc_deploy_key.encrypted_secret
}
