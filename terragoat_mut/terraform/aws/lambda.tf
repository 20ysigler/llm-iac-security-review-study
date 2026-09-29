resource "aws_lambda_function" "analytics_fn" {
  filename      = "resources/lambda_function_payload.zip"
  function_name = "${local.env_prefix.value}-analytics"
  role          = "${aws_iam_role.analytics_fn_role.arn}"
  handler       = "exports.test"

  source_code_hash = "${filebase64sha256("resources/lambda_function_payload.zip")}"

  runtime = "nodejs12.x"

  environment {
    variables = {
      access_key = "AKIAIOSFODNN7EXAMPLE"
      secret_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    }
  }
  tags = {
  }
}

resource "aws_iam_role" "analytics_fn_role" {
  name = "${local.env_prefix.value}-analytics-lambda"


  assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Effect": "Allow",
      "Sid": ""
    }
  ]
}
EOF
  tags = {
  }
}
