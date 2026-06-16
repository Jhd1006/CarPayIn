# ─── Carpayin VPC ───
resource "aws_route_table" "carpayin_public" {
  vpc_id = aws_vpc.carpayin.id
  tags = { Name = "Carpayin-public-rt" }
}

resource "aws_route_table" "carpayin_private_2a" {
  vpc_id = aws_vpc.carpayin.id
  tags = { Name = "Carpayin-private-2a-rt" }
}

resource "aws_route_table" "carpayin_private_2b" {
  vpc_id = aws_vpc.carpayin.id
  tags = { Name = "Carpayin-private-2b-rt" }
}

# ─── MockPG VPC ───
resource "aws_route_table" "mock_pg_public" {
  vpc_id = aws_vpc.mock_pg.id
  tags = { Name = "MockPG-public-rt" }
}

resource "aws_route_table" "mock_pg_private" {
  vpc_id = aws_vpc.mock_pg.id
  tags = { Name = "MockPG-private-rt" }
}

# ─── MockPMS VPC ───
resource "aws_route_table" "mock_pms_public" {
  vpc_id = aws_vpc.mock_pms.id
  tags = { Name = "MockPMS-public-rt" }
}

resource "aws_route_table" "mock_pms_private" {
  vpc_id = aws_vpc.mock_pms.id
  tags = { Name = "MockPMS-private-rt" }
}
