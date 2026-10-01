# Public ALB fronting the API (ADR-0017). HTTP only - Learner Lab has no ACM
# certificate / custom domain, so TLS terminates at CloudFront for the SPA and
# the API is reached over the ALB DNS name. A full account would add a 443
# listener with an ACM certificate.

resource "aws_lb" "api" {
  name               = "${local.name}-api"
  load_balancer_type = "application"
  subnets            = var.public_subnet_ids
  security_groups    = [var.alb_sg_id]
  tags               = { Name = "${local.name}-api" }
}

resource "aws_lb_target_group" "api" {
  name        = "${local.name}-api"
  port        = var.app_container_port
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  # Drain in 30s instead of the 300s default so scale-in / task replacement is
  # responsive during a spike test and deploys finish quickly.
  deregistration_delay = 30

  # Readiness probe: a task with an exhausted pool or failed migration returns
  # 503 here and is taken out of rotation, rather than the dependency-free
  # /healthz that would keep a broken task serving 500s. (Redis-down is not a
  # 503 - the app degrades to the DB count, ADR-0005.)
  health_check {
    path                = "/readyz"
    matcher             = "200"
    interval            = 15
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = { Name = "${local.name}-api" }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}
