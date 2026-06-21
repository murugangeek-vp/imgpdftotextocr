# ============================================================
# EKS Cluster — managed node groups (CPU + GPU)
# ============================================================
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = "${var.project_name}-eks"
  cluster_version = "1.30"

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  cluster_endpoint_public_access  = true
  cluster_endpoint_private_access = true

  # Cluster add-ons
  cluster_addons = {
    coredns                = { most_recent = true }
    kube-proxy             = { most_recent = true }
    vpc-cni                = { most_recent = true }
    aws-ebs-csi-driver     = { most_recent = true }
  }

  # ── CPU Node Group (services) ──────────────────────────
  eks_managed_node_groups = {
    cpu-workers = {
      name           = "cpu-workers"
      instance_types = var.eks_node_instance_types
      min_size       = var.eks_node_min_size
      max_size       = var.eks_node_max_size
      desired_size   = var.eks_node_min_size

      labels = {
        workload = "services"
      }
    }

    # ── GPU Node Group (Triton + OCR workers) ────────────
    gpu-workers = {
      name           = "gpu-workers"
      instance_types = var.eks_gpu_instance_types
      min_size       = 0
      max_size       = var.eks_gpu_max_size
      desired_size   = 0  # KEDA + Cluster Autoscaler manages this

      capacity_type = "SPOT"  # ~$0.40/hr vs $1.006/hr on-demand

      labels = {
        workload                       = "gpu-inference"
        "node.kubernetes.io/instance-type" = "g5.xlarge"
      }

      taints = [{
        key    = "nvidia.com/gpu"
        value  = "true"
        effect = "NO_SCHEDULE"
      }]

      # AMI with NVIDIA drivers pre-installed
      ami_type = "AL2_x86_64_GPU"
    }
  }

  # Allow KEDA, cert-manager, external-secrets IRSA
  enable_irsa = true
}

# OIDC provider for IRSA (IAM Roles for Service Accounts)
data "aws_eks_cluster" "this" {
  name       = module.eks.cluster_name
  depends_on = [module.eks]
}

data "aws_eks_cluster_auth" "this" {
  name       = module.eks.cluster_name
  depends_on = [module.eks]
}
