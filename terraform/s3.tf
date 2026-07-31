resource "aws_s3_bucket" "processed" {
  bucket = var.processed_bucket_name

  tags = {
    Name        = "Processed Data Bucket"
    Project     = "Qufoods Data Pipeline"
    ManagedBy   = "Terraform"
    Environment = "Development"
  }
}

resource "aws_s3_object" "lambda_zip" {
  bucket = aws_s3_bucket.lambda_code.id
  key    = "lambda.zip"
  source = "../build/lambda.zip"
}

resource "aws_s3_bucket_versioning" "processed" {
  bucket = aws_s3_bucket.processed.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "processed" {
  bucket = aws_s3_bucket.processed.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
