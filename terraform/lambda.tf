resource "aws_lambda_function" "processor" {

  function_name = var.lambda_function_name

  role = aws_iam_role.lambda_role.arn

  package_type = "Image"

  image_uri = var.lambda_image_uri #"${aws_ecr_repository.lambda.repository_url}:latest"

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
