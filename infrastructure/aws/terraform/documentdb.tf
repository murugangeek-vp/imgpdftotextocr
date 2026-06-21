# ============================================================
# DocumentDB (MongoDB-compatible) — job records + tier configs
# ============================================================
resource "aws_docdb_cluster" "this" {
  cluster_identifier     = "${var.project_name}-docdb"
  engine                 = "docdb"
  engine_version         = "5.0.0"

  master_username        = var.docdb_master_username
  master_password        = var.docdb_master_password

  db_subnet_group_name   = aws_docdb_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.docdb.id]

  storage_encrypted      = true
  kms_key_id             = aws_kms_key.main.arn

  backup_retention_period         = 7
  preferred_backup_window         = "02:00-04:00"
  preferred_maintenance_window    = "sun:04:00-sun:06:00"
  skip_final_snapshot             = false
  final_snapshot_identifier       = "${var.project_name}-docdb-final"

  enabled_cloudwatch_logs_exports = ["audit", "profiler"]
}

resource "aws_docdb_cluster_instance" "this" {
  count              = 2  # Primary + 1 replica
  identifier         = "${var.project_name}-docdb-${count.index}"
  cluster_identifier = aws_docdb_cluster.this.id
  instance_class     = var.docdb_instance_class
}

resource "aws_docdb_subnet_group" "this" {
  name       = "${var.project_name}-docdb-subnets"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_security_group" "docdb" {
  name_prefix = "${var.project_name}-docdb-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description     = "MongoDB from EKS"
    from_port       = 27017
    to_port         = 27017
    protocol        = "tcp"
    security_groups = [module.eks.cluster_security_group_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
