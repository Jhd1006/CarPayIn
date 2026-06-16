variable "region" {
  description = "AWS 리전"
  type        = string
  default     = "ap-northeast-2"
}

variable "carpayin_ami" {
  description = "Carpayin EC2 AMI ID"
  type        = string
  default     = "ami-0765f9741eedf9c7b"
}

variable "common_ami" {
  description = "공통 EC2 AMI ID"
  type        = string
  default     = "ami-0fc2b553b2bbfaee0"
}
