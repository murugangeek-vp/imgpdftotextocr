variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "ap-south-1"
}

variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string
  default     = "production"
}

variable "project_name" {
  description = "Project identifier used in resource naming"
  type        = string
  default     = "ocr-platform"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "eks_node_instance_types" {
  description = "EC2 instance types for EKS managed node group"
  type        = list(string)
  default     = ["t3.large"]
}

variable "eks_gpu_instance_types" {
  description = "GPU instance types for Triton inference"
  type        = list(string)
  default     = ["g5.xlarge"]
}

variable "eks_node_min_size" {
  type    = number
  default = 2
}

variable "eks_node_max_size" {
  type    = number
  default = 6
}

variable "eks_gpu_max_size" {
  description = "Max GPU nodes (KEDA-managed via Cluster Autoscaler)"
  type        = number
  default     = 10
}

variable "docdb_instance_class" {
  description = "DocumentDB instance class"
  type        = string
  default     = "db.r6g.large"
}

variable "docdb_master_username" {
  description = "DocumentDB master username"
  type        = string
  default     = "ocrdbadmin"
  sensitive   = true
}

variable "docdb_master_password" {
  description = "DocumentDB master password"
  type        = string
  sensitive   = true
}

variable "redis_node_type" {
  description = "ElastiCache Redis node type"
  type        = string
  default     = "cache.r6g.large"
}

variable "kafka_instance_type" {
  description = "MSK broker instance type"
  type        = string
  default     = "kafka.m5.large"
}

variable "cognito_callback_urls" {
  description = "Cognito OAuth callback URLs"
  type        = list(string)
  default     = ["https://ocrplatform.com/auth/callback"]
}

variable "cognito_logout_urls" {
  description = "Cognito logout redirect URLs"
  type        = list(string)
  default     = ["https://ocrplatform.com"]
}

variable "monthly_budget_limit" {
  description = "AWS Budget alert threshold in USD"
  type        = number
  default     = 200
}

variable "budget_alert_email" {
  description = "Email for AWS Budget alerts"
  type        = string
  default     = "admin@ocrplatform.com"
}
