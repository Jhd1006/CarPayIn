resource "aws_vpc" "carpayin" {
  cidr_block = "10.0.0.0/16"
  tags = {
    Name = "Carpayin-vpc"
  }
}

resource "aws_vpc" "mock_pg" {
  cidr_block = "10.1.0.0/16"
  tags = {
    Name = "MockPG-vpc"
  }
}

resource "aws_vpc" "mock_pms" {
  cidr_block = "10.2.0.0/16"
  tags = {
    Name = "MockPMS-vpc"
  }
}
