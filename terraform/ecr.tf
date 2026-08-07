resource "aws_ecr_repository" "lambda" {
  name = var.lambda_function_name

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Project     = "Qufoods Data Pipeline"
    Environment = "Development"
    ManagedBy   = "Terraform"
  }
}