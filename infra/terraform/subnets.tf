# ─── Carpayin VPC ───
resource "aws_subnet" "carpayin_public_2a" {
  vpc_id            = aws_vpc.carpayin.id
  cidr_block        = "10.0.0.0/20"
  availability_zone = "ap-northeast-2a"
  tags = { Name = "vpc-hd-subnet-public1-ap-northeast-2a" }
}

resource "aws_subnet" "carpayin_public_2b" {
  vpc_id            = aws_vpc.carpayin.id
  cidr_block        = "10.0.16.0/20"
  availability_zone = "ap-northeast-2b"
  tags = { Name = "vpc-hd-subnet-public2-ap-northeast-2b" }
}

resource "aws_subnet" "carpayin_private_2a" {
  vpc_id            = aws_vpc.carpayin.id
  cidr_block        = "10.0.128.0/20"
  availability_zone = "ap-northeast-2a"
  tags = { Name = "vpc-hd-subnet-private1-ap-northeast-2a" }
}

resource "aws_subnet" "carpayin_private_2b" {
  vpc_id            = aws_vpc.carpayin.id
  cidr_block        = "10.0.144.0/20"
  availability_zone = "ap-northeast-2b"
  tags = { Name = "vpc-hd-subnet-private2-ap-northeast-2b" }
}

# ─── MockPG VPC ───
resource "aws_subnet" "mock_pg_public_2a" {
  vpc_id            = aws_vpc.mock_pg.id
  cidr_block        = "10.1.0.0/20"
  availability_zone = "ap-northeast-2a"
  tags = { Name = "MockPG-public-subnet-2a" }
}

resource "aws_subnet" "mock_pg_public_2c" {
  vpc_id            = aws_vpc.mock_pg.id
  cidr_block        = "10.1.16.0/20"
  availability_zone = "ap-northeast-2c"
  tags = { Name = "MockPG-public-subnet-2c" }
}

resource "aws_subnet" "mock_pg_private_2a" {
  vpc_id            = aws_vpc.mock_pg.id
  cidr_block        = "10.1.128.0/20"
  availability_zone = "ap-northeast-2a"
  tags = { Name = "MockPG-private-subnet-2a" }
}

# ─── MockPMS VPC ───
resource "aws_subnet" "mock_pms_public_2a" {
  vpc_id            = aws_vpc.mock_pms.id
  cidr_block        = "10.2.0.0/20"
  availability_zone = "ap-northeast-2a"
  tags = { Name = "MockPMS-public-subnet-2a" }
}

resource "aws_subnet" "mock_pms_public_2c" {
  vpc_id            = aws_vpc.mock_pms.id
  cidr_block        = "10.2.16.0/20"
  availability_zone = "ap-northeast-2c"
  tags = { Name = "MockPMS-public-subnet-2c" }
}

resource "aws_subnet" "mock_pms_private_2a" {
  vpc_id            = aws_vpc.mock_pms.id
  cidr_block        = "10.2.128.0/20"
  availability_zone = "ap-northeast-2a"
  tags = { Name = "MockPMS-private-subnet-2a" }
}
