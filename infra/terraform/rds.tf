resource "aws_db_instance" "carpayin_postgresql" {
  identifier                  = "carpayin-postgresql"
  engine                      = "postgres"
  instance_class              = "db.t3.micro"
  multi_az                    = true
  username                    = "carpayin"
  password                    = "placeholder"
  storage_encrypted           = true
  copy_tags_to_snapshot       = true
  max_allocated_storage       = 1000
  performance_insights_enabled = true
  skip_final_snapshot         = true

  lifecycle {
    ignore_changes = [password]
  }
}
