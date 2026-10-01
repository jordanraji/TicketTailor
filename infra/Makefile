# TicketTailor infrastructure (ADR-0017). Requires an active Learner Lab session
# (credentials exported into the environment) before any AWS-touching target.
#
# Typical first deploy (the worker Lambda needs its image to exist before the
# full apply, so create the ECR repos first and push images into them):
#   make init ENV=dev
#   make plan ENV=dev           # dry run - creates nothing, validates creds + config
#   make repos ENV=dev          # create ONLY the ECR repos
#   make images TAG=latest      # build + push api/relay/worker into those repos
#   make apply ENV=dev          # create everything else
#   make smoke ENV=dev

ENV ?= dev
TAG ?= latest

.PHONY: fmt validate init plan repos apply destroy images web smoke output

fmt:
	terraform fmt -recursive

validate:
	terraform validate

init:
	terraform init
	terraform workspace select $(ENV) || terraform workspace new $(ENV)

plan:
	terraform workspace select $(ENV)
	terraform plan

# Create only the ECR repositories, so images can be pushed before the full
# apply (the worker Lambda validates its image at creation time).
repos:
	terraform workspace select $(ENV)
	terraform apply -target=module.registry

apply:
	terraform workspace select $(ENV)
	terraform apply

destroy:
	terraform workspace select $(ENV)
	terraform destroy

images:
	./scripts/build-and-push.sh $(TAG)

# Build the SPA against the deployed API URL and publish it to the S3 website
# bucket (ADR-0020). Run after 'make apply' with enable_frontend_website = true.
web:
	./scripts/deploy-web.sh

output:
	terraform output

# Hit the ALB health endpoint a few times.
smoke:
	@URL=$$(terraform output -raw api_healthcheck); \
	echo "GET $$URL"; \
	curl -fsS "$$URL" && echo "  OK" || echo "  FAILED"
