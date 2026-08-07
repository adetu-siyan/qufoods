import boto3
import json

# AWS config — region confirmed from SOW (S3 bucket is us-east-1)
AWS_REGION = "us-east-1"

# Model — Claude Haiku is the cheapest Bedrock model
# roughly $0.0003 per report summary — essentially free at this scale
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

# Hard cap on output tokens to control cost
# 200 tokens = roughly 3-4 sentences which is all we need
MAX_TOKENS = 200


def get_bedrock_client(aws_access_key_id, aws_secret_access_key):
    # Creates a Bedrock client using the provided credentials
    # We pass credentials explicitly rather than using a profile
    # so the app works without AWS CLI being configured
    return boto3.client(
        service_name="bedrock-runtime",
        region_name=AWS_REGION,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key
    )


def generate_narrative(prompt, aws_access_key_id, aws_secret_access_key):
    # Sends a prompt to Bedrock and returns the narrative text
    # Returns None if anything goes wrong — caller handles the fallback
    try:
        client = get_bedrock_client(aws_access_key_id, aws_secret_access_key)

        # Bedrock expects the request in this exact format for Claude models
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": MAX_TOKENS,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        })

        response = client.invoke_model(
            modelId=MODEL_ID,
            body=body,
            contentType="application/json",
            accept="application/json"
        )

        # Parse the response — Bedrock returns JSON with the text nested inside
        response_body = json.loads(response["body"].read())
        narrative = response_body["content"][0]["text"]
        return narrative.strip()

    # except Exception as e:
    #     # Silent failure — log the error but don't crash the report
    #     print(f"Bedrock narrative generation failed: {e}")
    #     return None
    except Exception as e:
        # Temporary — raise the error so we can see what's wrong
        raise e


def build_branch_prompt(metrics):
    # Builds the prompt for the branch manager report narrative
    # metrics is a dict of key numbers from the report
    return f"""
You are a data analyst writing a brief executive summary for a branch manager 
at a Nigerian quick-service restaurant chain called QuFoods.

Write 2-3 sentences summarising the following branch performance metrics.
Be direct and highlight what needs attention. Use plain business language.
Do not use bullet points. Do not repeat the numbers back verbatim.

Metrics:
- Total revenue: {metrics.get('total_revenue', 'N/A')}
- Total transactions: {metrics.get('transactions', 'N/A')}
- Average order value: {metrics.get('avg_order_value', 'N/A')}
- Failed transactions: {metrics.get('failed_transactions', 'N/A')}
- Top selling item: {metrics.get('top_item', 'N/A')}
- Most used payment method: {metrics.get('top_payment', 'N/A')}

Write the summary now:
""".strip()


def build_regional_prompt(metrics):
    return f"""
You are a data analyst writing a brief executive summary for a regional manager
at a Nigerian quick-service restaurant chain called QuFoods.

Write 2-3 sentences summarising the following regional performance metrics.
Focus on branch comparisons and flag any concerns. Use plain business language.
Do not use bullet points. Do not repeat the numbers back verbatim.

Metrics:
- Total regional revenue: {metrics.get('total_revenue', 'N/A')}
- Number of active branches: {metrics.get('branches_active', 'N/A')}
- Top performing branch: {metrics.get('top_branch', 'N/A')}
- Lowest performing branch: {metrics.get('bottom_branch', 'N/A')}
- Total regional expenses: {metrics.get('total_expenses', 'N/A')}
- Membership penetration rate: {metrics.get('membership_rate', 'N/A')}

Write the summary now:
""".strip()


def build_operations_prompt(metrics):
    return f"""
You are a data analyst writing a brief executive summary for the Head of Operations
at a Nigerian quick-service restaurant chain called QuFoods.

Write 2-3 sentences summarising the following network-wide performance metrics.
Focus on overall health and flag any systemic concerns. Use plain business language.
Do not use bullet points. Do not repeat the numbers back verbatim.

Metrics:
- Total network revenue: {metrics.get('total_revenue', 'N/A')}
- Total network expenses: {metrics.get('total_expenses', 'N/A')}
- Total transactions: {metrics.get('total_transactions', 'N/A')}
- Active branches: {metrics.get('branches_active', 'N/A')}
- Top branch: {metrics.get('top_branch', 'N/A')}
- Bottom branch: {metrics.get('bottom_branch', 'N/A')}
- Failed transaction rate: {metrics.get('failed_rate', 'N/A')}

Write the summary now:
""".strip()