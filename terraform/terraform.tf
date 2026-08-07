terraform {
  required_version = ">= 1.7"

  backend "s3" {
        bucket = "qufoods-terraform-state"
        key    = "qufoods/lambda/terraform.tfstate"
        region = "us-east-1"
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }

#     archive = {
#       source  = "hashicorp/archive"
#       version = "~> 2.5"
#     }
  }
}
