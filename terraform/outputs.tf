output "processed_bucket_name" {

  value = aws_s3_bucket.processed.bucket

}

output "lambda_name" {

  value = aws_lambda_function.processor.function_name

}

output "lambda_arn" {

  value = aws_lambda_function.processor.arn

}

output "eventbridge_rule" {

  value = aws_cloudwatch_event_rule.every_five_minutes.name

}
