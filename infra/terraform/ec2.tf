resource "aws_instance" "gitlab_runner" {
  ami           = "ami-0765f9741eedf9c7b"
  instance_type = "t3.small"
  subnet_id     = aws_subnet.carpayin_public_2a.id
  tags = { Name = "gitlab-runner" }
}

resource "aws_instance" "mock_pms_db" {
  ami           = "ami-0fc2b553b2bbfaee0"
  instance_type = "t3.micro"
  subnet_id     = aws_subnet.mock_pms_private_2a.id
  tags = { Name = "MockPMS-db" }
}

resource "aws_instance" "mock_pms_server" {
  ami           = "ami-0fc2b553b2bbfaee0"
  instance_type = "t3.micro"
  subnet_id     = aws_subnet.mock_pms_private_2a.id
  tags = { Name = "MockPMS-server" }
}

resource "aws_instance" "mock_pg_db" {
  ami           = "ami-0fc2b553b2bbfaee0"
  instance_type = "t3.micro"
  subnet_id     = aws_subnet.mock_pg_private_2a.id
  tags = { Name = "MockPG-db" }
}

resource "aws_instance" "mock_pg_server" {
  ami           = "ami-0fc2b553b2bbfaee0"
  instance_type = "t3.micro"
  subnet_id     = aws_subnet.mock_pg_private_2a.id
  tags = { Name = "MockPG-server" }
}

resource "aws_instance" "wireguard" {
  ami              = "ami-0fc2b553b2bbfaee0"
  instance_type    = "t3.micro"
  subnet_id        = aws_subnet.mock_pg_public_2a.id
  source_dest_check = false
  tags = { Name = "wireguard-with-openstack" }
}
