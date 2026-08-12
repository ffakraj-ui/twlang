"""
TW Framework - Infrastructure as Code

Implements:
14. Terraform-based infrastructure for AWS (VPC, ECS, ECR, ALB, S3, CloudFront, WAF, Redis)
"""

from __future__ import annotations
import json, logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AWSConfig:
    """AWS infrastructure configuration."""
    region: str = "ap-south-1"
    project_name: str = "tw-framework"
    environment: str = "production"  # production | staging | dev

    # VPC
    vpc_cidr: str = "10.0.0.0/16"
    availability_zones: List[str] = field(default_factory=lambda: ["ap-south-1a", "ap-south-1b"])

    # ECS
    ecs_desired_count: int = 2
    ecs_cpu: int = 512
    ecs_memory: int = 1024
    container_port: int = 3000

    # ECR
    ecr_image_tag: str = "latest"

    # ALB
    alb_certificate_arn: str = ""

    # S3 / CloudFront
    s3_bucket_name: str = ""
    cloudfront_price_class: str = "PriceClass_200"

    # Redis
    redis_node_type: str = "cache.t3.micro"
    redis_cluster_size: int = 2


class TerraformGenerator:
    """Generates Terraform infrastructure code for AWS deployment.

    Generates:
    - VPC with public/private subnets across multiple AZs
    - ECS Fargate cluster for container orchestration
    - ECR repository for container images
    - Application Load Balancer with HTTPS
    - S3 + CloudFront for static asset delivery
    - WAF for web application firewall
    - ElastiCache Redis for session/cache storage
    - CI/CD ready configuration
    """

    def __init__(self, config: Optional[AWSConfig] = None):
        self.config = config or AWSConfig()

    def generate_vpc(self) -> str:
        """Generate VPC Terraform configuration."""
        return """# VPC Configuration
resource "aws_vpc" "main" {
  cidr_block           = "{vpc_cidr}"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags = {{
    Name        = "{project}-vpc"
    Environment = "{env}"
  }}
}}

# Public Subnets
resource "aws_subnet" "public" {{
  count             = {az_count}
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(aws_vpc.main.cidr_block, 8, count.index)
  availability_zone = "{azs}"
  map_public_ip_address = true
  tags = {{ Name = "{project}-public-${{count.index + 1}}" }}
}}

# Private Subnets
resource "aws_subnet" "private" {{
  count             = {az_count}
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(aws_vpc.main.cidr_block, 8, count.index + 10)
  availability_zone = "{azs}"
  tags = {{ Name = "{project}-private-${{count.index + 1}}" }}
}}

# Internet Gateway
resource "aws_internet_gateway" "main" {{
  vpc_id = aws_vpc.main.id
  tags = {{ Name = "{project}-igw" }}
}}

# NAT Gateway
resource "aws_nat_gateway" "main" {{
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id
  depends_on    = [aws_internet_gateway.main]
  tags = {{ Name = "{project}-nat" }}
}}

resource "aws_eip" "nat" {{
  domain = "vpc"
}}
""".format(
            vpc_cidr=self.config.vpc_cidr,
            project=self.config.project_name,
            env=self.config.environment,
            az_count=len(self.config.availability_zones),
            azs=self.config.availability_zones[0],
        )

    def generate_ecs(self) -> str:
        """Generate ECS Fargate configuration."""
        return """# ECS Cluster
resource "aws_ecs_cluster" "main" {{
  name = "{project}-cluster"
  setting {{
    name  = "containerInsights"
    value = "enabled"
  }}
}}

# ECR Repository
resource "aws_ecr_repository" "app" {{
  name                 = "{project}"
  image_tag_mutability = "MUTABLE"
  image_scanning_configuration {{
    scan_on_push = true
  }}
}}

# ECS Task Definition
resource "aws_ecs_task_definition" "app" {{
  family                   = "{project}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = {cpu}
  memory                   = {memory}
  container_definitions = jsonencode([{{
    name  = "{project}"
    image = "${{aws_ecr_repository.app.repository_url}}:{tag}"
    portMappings = [{{
      containerPort = {port}
      protocol      = "tcp"
    }}]
    environment = [
      {{ name = "NODE_ENV", value = "{env}" }}
    ]
    logConfiguration = {{
      logDriver = "awslogs"
      options = {{
        "awslogs-group"         = "/ecs/{project}"
        "awslogs-region"        = "{region}"
        "awslogs-stream-prefix" = "ecs"
      }}
    }}
  }}])
}}

# ECS Service
resource "aws_ecs_service" "app" {{
  name            = "{project}-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = {desired}
  launch_type     = "FARGATE"

  network_configuration {{
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }}

  load_balancer {{
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "{project}"
    container_port   = {port}
  }}

  depends_on = [aws_lb_listener.app]
}}
""".format(
            project=self.config.project_name,
            cpu=self.config.ecs_cpu,
            memory=self.config.ecs_memory,
            tag=self.config.ecr_image_tag,
            port=self.config.container_port,
            env=self.config.environment,
            region=self.config.region,
            desired=self.config.ecs_desired_count,
        )

    def generate_alb(self) -> str:
        """Generate Application Load Balancer configuration."""
        return """# Application Load Balancer
resource "aws_lb" "main" {{
  name               = "{project}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  enable_deletion_protection = {env} == "production"
  tags = {{ Name = "{project}-alb" }}
}}

# Target Group
resource "aws_lb_target_group" "app" {{
  name        = "{project}-tg"
  port        = {port}
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {{
    enabled             = true
    path                = "/health/ready"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    matcher             = "200"
  }}
}}

# HTTPS Listener
resource "aws_lb_listener" "https" {{
  load_balancer_arn = aws_lb.main.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn

  default_action {{
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }}
}}

# HTTP -> HTTPS Redirect
resource "aws_lb_listener" "http" {{
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {{
    type = "redirect"
    redirect {{
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }}
  }}
}}
""".format(
            project=self.config.project_name,
            port=self.config.container_port,
            env="true" if self.config.environment == "production" else "false",
        )

    def generate_s3_cloudfront(self) -> str:
        """Generate S3 + CloudFront for static assets."""
        return """# S3 Bucket for Static Assets
resource "aws_s3_bucket" "assets" {{
  bucket = "{bucket}"
  tags   = {{ Name = "{project}-assets" }}
}}

# S3 Bucket Versioning
resource "aws_s3_bucket_versioning" "assets" {{
  bucket = aws_s3_bucket.assets.id
  versioning_configuration {{
    status = "Enabled"
  }}
}}

# CloudFront Distribution
resource "aws_cloudfront_distribution" "assets" {{
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  price_class         = "{price_class}"

  origin {{
    domain_name = aws_s3_bucket.assets.bucket_regional_domain_name
    origin_id   = "S3-{project}-assets"
  }}

  default_cache_behavior {{
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-{project}-assets"

    forwarded_values {{
      query_string = false
      cookies {{ forward = "none" }}
    }}

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
    compress               = true
  }}

  restrictions {{
    geo_restriction {{
      restriction_type = "none"
    }}
  }}

  viewer_certificate {{
    cloudfront_default_certificate = true
  }}

  tags = {{ Name = "{project}-cdn" }}
}}
""".format(
            bucket=self.config.s3_bucket_name or self.config.project_name + "-assets",
            project=self.config.project_name,
            price_class=self.config.cloudfront_price_class,
        )

    def generate_redis(self) -> str:
        """Generate ElastiCache Redis configuration."""
        return """# Redis Subnet Group
resource "aws_elasticache_subnet_group" "redis" {{
  name        = "{project}-redis-subnet"
  subnet_ids  = aws_subnet.private[*].id
}}

# Redis Replication Group
resource "aws_elasticache_replication_group" "main" {{
  replication_group_id          = "{project}-redis"
  replication_group_description = "Redis for {project}"
  node_type                     = "{node_type}"
  number_cache_clusters         = {cluster_size}
  subnet_group_name             = aws_elasticache_subnet_group.redis.name
  security_group_ids            = [aws_security_group.redis.id]
  automatic_failover_enabled   = true
  at_rest_encryption_enabled    = true
  transit_encryption_enabled    = true
  multi_az_enabled              = {cluster_size} > 1

  tags = {{ Name = "{project}-redis" }}
}}
""".format(
            project=self.config.project_name,
            node_type=self.config.redis_node_type,
            cluster_size=self.config.redis_cluster_size,
        )

    def generate_waf(self) -> str:
        """Generate WAF Web ACL."""
        return """# WAF Web ACL
resource "aws_wafv2_web_acl" "main" {{
  name        = "{project}-waf"
  description = "WAF for {project}"
  scope       = "REGIONAL"

  default_action {{
    allow {{}}
  }}

  rule {{
    name     = "RateLimitRule"
    priority = 1
    action {{
      block {{}}
    }}
    statement {{
      rate_based_statement {{
        limit              = 2000
        aggregate_key_type = "IP"
      }}
    }}
    visibility_config {{
      cloudwatch_metrics_enabled = true
      metric_name                = "RateLimitRule"
      sampled_requests_enabled   = true
    }}
  }}

  rule {{
    name     = "SQLiRule"
    priority = 2
    action {{ block {{}} }}
    statement {{
      sqli_match_statement {{
        field_to_match {{ all_query_arguments {{}} }}
        text_transformation {{ priority = 0 type = "URL_DECODE" }}
      }}
    }}
    visibility_config {{
      cloudwatch_metrics_enabled = true
      metric_name                = "SQLiRule"
      sampled_requests_enabled   = true
    }}
  }}

  rule {{
    name     = "XSSRule"
    priority = 3
    action {{ block {{}} }}
    statement {{
      xss_match_statement {{
        field_to_match {{ all_query_arguments {{}} }}
        text_transformation {{ priority = 0 type = "URL_DECODE" }}
      }}
    }}
    visibility_config {{
      cloudwatch_metrics_enabled = true
      metric_name                = "XSSRule"
      sampled_requests_enabled   = true
    }}
  }}

  visibility_config {{
    cloudwatch_metrics_enabled = true
    metric_name                = "{project}-waf"
    sampled_requests_enabled   = true
  }}

  tags = {{ Name = "{project}-waf" }}
}}

# Associate WAF with ALB
resource "aws_wafv2_web_acl_association" "alb" {{
  resource_arn = aws_lb.main.arn
  web_acl_arn  = aws_wafv2_web_acl.main.arn
}}
""".format(project=self.config.project_name)

    def generate_all(self) -> Dict[str, str]:
        """Generate all Terraform files."""
        return {
            "vpc.tf": self.generate_vpc(),
            "ecs.tf": self.generate_ecs(),
            "alb.tf": self.generate_alb(),
            "s3_cloudfront.tf": self.generate_s3_cloudfront(),
            "redis.tf": self.generate_redis(),
            "waf.tf": self.generate_waf(),
        }

    def write_terraform(self, output_dir: str = "terraform") -> List[str]:
        """Write all Terraform files to a directory."""
        import os
        os.makedirs(output_dir, exist_ok=True)
        written = []
        for filename, content in self.generate_all().items():
            path = os.path.join(output_dir, filename)
            with open(path, "w") as f:
                f.write(content)
            written.append(path)
        return written

    def get_summary(self) -> Dict[str, Any]:
        return {
            "region": self.config.region,
            "environment": self.config.environment,
            "components": ["VPC", "ECS", "ECR", "ALB", "S3", "CloudFront", "WAF", "Redis"],
            "availability_zones": len(self.config.availability_zones),
            "ecs_instances": self.config.ecs_desired_count,
            "redis_cluster_size": self.config.redis_cluster_size,
        }


__all__ = ["AWSConfig", "TerraformGenerator"]
