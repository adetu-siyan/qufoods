resource "aws_cloudwatch_event_rule" "every_five_minutes" {

  name                = "${var.lambda_function_name}-schedule"

  description         = "Runs the Lambda every hour"

  schedule_expression = "rate(1 hour)"

}
resource "aws_cloudwatch_event_target" "lambda_target" {

  rule = aws_cloudwatch_event_rule.every_five_minutes.name

  target_id = "ProcessData"

  arn = aws_lambda_function.processor.arn

}
resource "aws_lambda_permission" "allow_eventbridge" {

  statement_id = "AllowExecutionFromEventBridge"

  action = "lambda:InvokeFunction"

  function_name = aws_lambda_function.processor.function_name

  principal = "events.amazonaws.com"

  source_arn = aws_cloudwatch_event_rule.every_five_minutes.arn

}
