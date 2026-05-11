terraform {
  required_version = ">= 1.9"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.44"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
  }

  # Uncomment and configure once the bootstrap bucket exists.
  # backend "s3" {
  #   bucket  = "worley-uaip-tfstate"
  #   key     = "uaip-bedrock-agent/terraform.tfstate"
  #   region  = "ap-southeast-2"
  #   encrypt = true
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      project     = "uaip"
      workload    = "uc2"
      component   = "aws-agent-gateway"
      managed-by  = "terraform"
      environment = var.environment
    }
  }
}
