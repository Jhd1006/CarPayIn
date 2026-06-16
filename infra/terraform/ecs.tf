resource "aws_ecs_cluster" "hd_ecs_cluster" {
  name = "hd-ecs-cluster"

  configuration {
    execute_command_configuration {
      logging = "DEFAULT"
    }
  }
}

resource "aws_ecs_service" "carpayin_backend" {
  name                          = "hd-carpayin-backend-td-service-atz8o6xv"
  cluster                       = aws_ecs_cluster.hd_ecs_cluster.id
  task_definition               = "hd-carpayin-backend-td:25"
  desired_count                 = 1
  launch_type                   = "FARGATE"
  availability_zone_rebalancing = "ENABLED"
  enable_ecs_managed_tags       = true

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  load_balancer {
    container_name   = "hd-carpayin-backend-container"
    container_port   = 8000
    target_group_arn = "arn:aws:elasticloadbalancing:ap-northeast-2:353488928095:targetgroup/Carpayin-internal-tg/d263f64f7f28453c"
  }

  load_balancer {
    container_name   = "hd-carpayin-backend-container"
    container_port   = 8000
    target_group_arn = "arn:aws:elasticloadbalancing:ap-northeast-2:353488928095:targetgroup/Carpayin-public-tg/8792f68f615b1f25"
  }

  network_configuration {
    assign_public_ip = false
    security_groups  = ["sg-0cb4087d6af294166"]
    subnets          = ["subnet-0268f385eda4be418", "subnet-0fc2ebb72070bd5db"]
  }
}
