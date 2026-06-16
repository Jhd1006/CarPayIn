resource "aws_internet_gateway" "carpayin" {
  vpc_id = aws_vpc.carpayin.id
  tags = { Name = "vpc-hd-igw" }
}

resource "aws_internet_gateway" "mock_pg" {
  vpc_id = aws_vpc.mock_pg.id
  tags = { Name = "MockPG-igw" }
}

resource "aws_internet_gateway" "mock_pms" {
  vpc_id = aws_vpc.mock_pms.id
  tags = { Name = "MockPMS-igw" }
}
