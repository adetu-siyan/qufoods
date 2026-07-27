variable "aws_region" {
  description = "AWS deployment region"
  type        = string
  default     = "us-east-1"
}

variable "raw_bucket_name" {
  description = "Existing raw bucket"
  type        = string
  default     = "qufoods-raw"
}

variable "processed_bucket_name" {
  description = "Processed data bucket"
  type        = string
}

variable "lambda_function_name" {
  type    = string
  default = "qufoods-data-processor"
}

variable "lambda_runtime" {
  type    = string
  default = "python3.12"
}

variable "lambda_handler" {
  type    = string
  default = "handler.the_lambda_handler"
}

variable "lambda_zip_path" {
  description = "Path to deployment zip"
  type        = string
  default     = "../build/lambda.zip"
}

variable "db_host" {
  type = string
}

variable "db_port" {
  type = string
}

variable "db_name" {
  type = string
}

variable "db_username" {
  type = string
}

variable "db_password" {
  type      = string
  sensitive = true
}
