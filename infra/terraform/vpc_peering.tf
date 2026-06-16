resource "aws_vpc_peering_connection" "carpayin_mockpms" {
  vpc_id      = aws_vpc.carpayin.id
  peer_vpc_id = aws_vpc.mock_pms.id
  tags = { Name = "carpayin-mockpms" }
}

resource "aws_vpc_peering_connection" "carpayin_mockpg" {
  vpc_id      = aws_vpc.carpayin.id
  peer_vpc_id = aws_vpc.mock_pg.id
  tags = { Name = "carpayin-mockpg" }
}
