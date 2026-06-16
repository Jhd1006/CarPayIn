resource "aws_instance" "gitlab_runner" {
  ami           = var.carpayin_ami
  instance_type = "t3.small"
  subnet_id     = aws_subnet.carpayin_public_2a.id
  tags = { Name = "gitlab-runner" }
}

resource "aws_instance" "mock_pms_db" {
  ami           = var.common_ami
  instance_type = "t3.micro"
  subnet_id     = aws_subnet.mock_pms_private_2a.id
  tags = { Name = "MockPMS-db" }
}

resource "aws_instance" "mock_pms_server" {
  ami           = var.common_ami
  instance_type = "t3.micro"
  subnet_id     = aws_subnet.mock_pms_private_2a.id
  tags = { Name = "MockPMS-server" }
}

resource "aws_instance" "mock_pg_db" {
  ami           = var.common_ami
  instance_type = "t3.micro"
  subnet_id     = aws_subnet.mock_pg_private_2a.id
  tags = { Name = "MockPG-db" }
}

resource "aws_instance" "mock_pg_server" {
  ami           = var.common_ami
  instance_type = "t3.micro"
  subnet_id     = aws_subnet.mock_pg_private_2a.id
  tags = { Name = "MockPG-server" }
}

resource "aws_instance" "wireguard" {
  ami               = var.common_ami
  instance_type     = "t3.micro"
  subnet_id         = aws_subnet.mock_pg_public_2a.id
  source_dest_check = false
  tags = { Name = "wireguard-with-openstack" }
}
