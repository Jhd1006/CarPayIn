# VPC
output "carpayin_vpc_id" {
  description = "Carpayin VPC ID"
  value       = aws_vpc.carpayin.id
}

output "mock_pg_vpc_id" {
  description = "MockPG VPC ID"
  value       = aws_vpc.mock_pg.id
}

output "mock_pms_vpc_id" {
  description = "MockPMS VPC ID"
  value       = aws_vpc.mock_pms.id
}

# Subnets
output "carpayin_private_subnet_2a_id" {
  description = "Carpayin Private Subnet 2a ID"
  value       = aws_subnet.carpayin_private_2a.id
}

output "carpayin_private_subnet_2b_id" {
  description = "Carpayin Private Subnet 2b ID"
  value       = aws_subnet.carpayin_private_2b.id
}

# EC2
output "wireguard_public_ip" {
  description = "WireGuard EC2 Public IP"
  value       = aws_instance.wireguard.public_ip
}

# RDS
output "rds_endpoint" {
  description = "RDS PostgreSQL 엔드포인트"
  value       = aws_db_instance.carpayin_postgresql.endpoint
}

# ElastiCache
output "carpayin_redis_endpoint" {
  description = "Carpayin Redis Serverless 엔드포인트"
  value       = aws_elasticache_serverless_cache.carpayin_redis.endpoint
}

# ECS
output "ecs_cluster_arn" {
  description = "ECS 클러스터 ARN"
  value       = aws_ecs_cluster.hd_ecs_cluster.arn
}
