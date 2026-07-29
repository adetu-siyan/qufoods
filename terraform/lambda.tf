resource "aws_lambda_function" "processor" {

  function_name = var.lambda_function_name

  role = aws_iam_role.lambda_role.arn

  runtime = var.lambda_runtime

  handler = var.lambda_handler

  filename = var.lambda_zip_path

  source_code_hash = filebase64sha256(var.lambda_zip_path)

  timeout = 300

  memory_size = 2048

  architectures = ["x86_64"]

  environment {

    variables = {

      RAW_BUCKET = var.raw_bucket_name

      PROCESSED_BUCKET = aws_s3_bucket.processed.bucket

      DB_HOST = var.db_host

      DB_PORT = var.db_port

      DB_NAME = var.db_name

      DB_USERNAME = var.db_username

      DB_PASSWORD = var.db_password

    }

  }

  depends_on = [

    aws_iam_role_policy_attachment.lambda_attachment

  ]

}
