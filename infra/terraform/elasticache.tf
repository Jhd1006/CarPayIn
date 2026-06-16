resource "aws_elasticache_serverless_cache" "carpayin_redis" {
  engine = "valkey"
  name   = "carpayin-redis"
}

resource "aws_elasticache_replication_group" "mockpms_redis" {
  replication_group_id = "mockpms-redis"
  description          = "CarPay-in Mock PMS ElastiCache Redis"
  engine               = "valkey"

  lifecycle {
    ignore_changes = [auth_token_update_strategy]
  }
}
