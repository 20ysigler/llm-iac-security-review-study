resource "aws_db_subnet_group" "catalog_db_subnets" {
  name        = "catalogsg-${local.env_prefix.value}"
  subnet_ids  = ["${aws_subnet.portal_subnet_a.id}", "${aws_subnet.portal_subnet_b.id}"]
  description = "Terraform DB Subnet Group"

  tags = {
    Name        = "catalogsg-${local.env_prefix.value}"
    Environment = local.env_prefix.value
    }
}

output "catalog_db_endpoint" {
  value       = aws_db_instance.catalog_db.endpoint
  description = "DB Endpoint"
}

resource "aws_iam_instance_profile" "catalog_app_profile" {
  name = "${local.env_prefix.value}-catalcatalogopts-profile"
  role = "${aws_iam_role.catalog_app_role.name}"
  tags = {
  }
}

resource "aws_db_parameter_group" "catalog_db_params" {
  name        = "catalogparams-${local.env_prefix.value}"
  family      = "mysql8.0"
  description = "Terraform PG"

  parameter {
    name         = "character_set_client"
    value        = "utf8"
    apply_method = "immediate"
  }

  parameter {
    name         = "character_set_server"
    value        = "utf8"
    apply_method = "immediate"
  }

  tags = {
    Name        = "${local.env_prefix.value}-catalogparams"
    Environment = local.env_prefix.value
    }
}

resource "aws_iam_role" "catalog_app_role" {
  name = "${local.env_prefix.value}-catalcatalogopts-role"
  path = "/"

  assume_role_policy = <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Action": "sts:AssumeRole",
            "Principal": {
               "Service": "ec2.amazonaws.com"
            },
            "Effect": "Allow",
            "Sid": ""
        }
    ]
}
EOF

  tags = {
    Name        = "${local.env_prefix.value}-catalcatalogopts-role"
    Environment = local.env_prefix.value
    }
}

resource "aws_instance" "catalog_app_server" {
  instance_type        = "t2.nano"
  iam_instance_profile = aws_iam_instance_profile.catalog_app_profile.name
  ami                  = data.aws_ami.base_image.id

  vpc_security_group_ids = [
  "${aws_security_group.portal_sg.id}"]
  subnet_id = "${aws_subnet.portal_subnet_a.id}"
  user_data = <<EOF
#! /bin/bash
### Config from https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_Tutorials.WebServerDB.CreateWebServer.html
sudo yum -y update
sudo yum -y install httpd php php-mysqlnd
sudo systemctl enable httpd 
sudo systemctl start httpd

sudo mkdir /var/www/inc
cat << EnD > /tmp/dbinfo.inc
<?php
define('DB_SERVER', '${aws_db_instance.catalog_db.endpoint}');
define('DB_USERNAME', '${aws_db_instance.catalog_db.username}');
define('DB_PASSWORD', '${var.password}');
define('DB_DATABASE', '${aws_db_instance.catalog_db.name}');
?>
EnD
sudo mv /tmp/dbinfo.inc /var/www/inc 
sudo chown root:root /var/www/inc/dbinfo.inc

cat << EnD > /tmp/index.php
<?php include "../inc/dbinfo.inc"; ?>
<html>
<body>
<h1>Sample page</h1>
<?php

  /* Connect to MySQL and select the database. */
  \$connection = mysqli_connect(DB_SERVER, DB_USERNAME, DB_PASSWORD);

  if (mysqli_connect_errno()) echo "Failed to connect to MySQL: " . mysqli_connect_error();

  \$database = mysqli_select_db(\$connection, DB_DATABASE);

  /* Ensure that the EMPLOYEES table exists. */
  VerifyEmployeesTable(\$connection, DB_DATABASE);

  /* If input fields are populated, add a row to the EMPLOYEES table. */
  \$employee_name = htmlentities(\$_POST['NAME']);
  \$employee_address = htmlentities(\$_POST['ADDRESS']);

  if (strlen(\$employee_name) || strlen(\$employee_address)) {
    AddEmployee(\$connection, \$employee_name, \$employee_address);
  }
?>

<!-- Input form -->
<form action="<?PHP echo \$_SERVER['SCRIPT_NAME'] ?>" method="POST">
  <table border="0">
    <tr>
      <td>NAME</td>
      <td>ADDRESS</td>
    </tr>
    <tr>
      <td>
        <input type="text" name="NAME" maxlength="45" size="30" />
      </td>
      <td>
        <input type="text" name="ADDRESS" maxlength="90" size="60" />
      </td>
      <td>
        <input type="submit" value="Add Data" />
      </td>
    </tr>
  </table>
</form>

<!-- Display table data. -->
<table border="1" cellpadding="2" cellspacing="2">
  <tr>
    <td>ID</td>
    <td>NAME</td>
    <td>ADDRESS</td>
  </tr>

<?php

\$result = mysqli_query(\$connection, "SELECT * FROM EMPLOYEES");

while(\$query_data = mysqli_fetch_row(\$result)) {
  echo "<tr>";
  echo "<td>",\$query_data[0], "</td>",
       "<td>",\$query_data[1], "</td>",
       "<td>",\$query_data[2], "</td>";
  echo "</tr>";
}
?>

</table>

<!-- Clean up. -->
<?php

  mysqli_free_result(\$result);
  mysqli_close(\$connection);

?>

</body>
</html>


<?php

/* Add an employee to the table. */
function AddEmployee(\$connection, \$name, \$address) {
   \$n = mysqli_real_escape_string(\$connection, \$name);
   \$a = mysqli_real_escape_string(\$connection, \$address);

   \$query = "INSERT INTO EMPLOYEES (NAME, ADDRESS) VALUES ('\$n', '\$a');";

   if(!mysqli_query(\$connection, \$query)) echo("<p>Error adding employee data.</p>");
}

/* Check whether the table exists and, if not, create it. */
function VerifyEmployeesTable(\$connection, \$dbName) {
  if(!TableExists("EMPLOYEES", \$connection, \$dbName))
  {
     \$query = "CREATE TABLE EMPLOYEES (
         ID int(11) UNSIGNED AUTO_INCREMENT PRIMARY KEY,
         NAME VARCHAR(45),
         ADDRESS VARCHAR(90)
       )";

     if(!mysqli_query(\$connection, \$query)) echo("<p>Error creating table.</p>");
  }
}

/* Check for the existence of a table. */
function TableExists(\$tableName, \$connection, \$dbName) {
  \$t = mysqli_real_escape_string(\$connection, \$tableName);
  \$d = mysqli_real_escape_string(\$connection, \$dbName);

  \$checktable = mysqli_query(\$connection,
      "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_NAME = '\$t' AND TABLE_SCHEMA = '\$d'");

  if(mysqli_num_rows(\$checktable) > 0) return true;

  return false;
}
?>               
EnD

sudo mv /tmp/index.php /var/www/html
sudo chown root:root /var/www/html/index.php



EOF
  tags = {
    Name = "${local.env_prefix.value}-catalcatalogopts-app"
    }
}

resource "aws_db_instance" "catalog_db" {

  name                   = var.dbname
  parameter_group_name   = aws_db_parameter_group.catalog_db_params.name
  engine                 = "mysql"
  db_subnet_group_name   = aws_db_subnet_group.catalog_db_subnets.name
  option_group_name      = aws_db_option_group.catalog_db_options.name
  vpc_security_group_ids = ["${aws_security_group.catalog_db_sg.id}"]

  identifier              = "catalcatalogopts-${local.env_prefix.value}"
  password                = var.password
  apply_immediately       = true
  monitoring_interval     = 0
  backup_retention_period = 0
  publicly_accessible     = true
  multi_az                = false
  storage_encrypted       = false
  skip_final_snapshot     = true
  allocated_storage       = "20"
  username                = "admin"
  instance_class          = "db.t3.micro"
  engine_version          = "8.0" # Latest major version 

  tags = {
    Name        = "${local.env_prefix.value}-catalog"
    Environment = local.env_prefix.value
    }

  lifecycle {
    ignore_changes = ["password"]
  }
}

output "catalog_app_public_dns" {
  description = "DB Public DNS name"
  value       = aws_instance.catalog_app_server.public_dns
}

resource "aws_security_group" "catalog_db_sg" {
  name   = "${local.env_prefix.value}-catalcatalogopts-portal-sg"
  vpc_id = aws_vpc.portal_vpc.id

  tags = {
    Name        = "${local.env_prefix.value}-catalcatalogopts-portal-sg"
    Environment = local.env_prefix.value
    }
}

resource "aws_security_group_rule" "catalog_db_outbound" {
  to_port           = 0
  type              = "egress"
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  from_port         = 0
  security_group_id = "${aws_security_group.catalog_db_sg.id}"
}

resource "aws_iam_role_policy" "catalog_app_policy" {
  name = "${local.env_prefix.value}-catalcatalogopts-policy"
  role = aws_iam_role.catalog_app_role.id

  policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": [
        "s3:*",
        "ec2:*",
        "rds:*"
      ],
      "Effect": "Allow",
      "Resource": "*"
    }
  ]
}
EOF
}

resource "aws_security_group_rule" "catalog_db_inbound" {
  type              = "ingress"
  from_port         = "3306"
  protocol          = "tcp"
  to_port           = "3306"
  cidr_blocks       = ["${aws_vpc.portal_vpc.cidr_block}"]
  security_group_id = aws_security_group.catalog_db_sg.id
}

data "aws_ami" "base_image" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "owner-alias"
    values = ["amazon"]
  }

  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-portal-disk"]
  }
}

resource "aws_db_option_group" "catalog_db_options" {
  engine_name              = "mysql"
  name                     = "catalogopts-${local.env_prefix.value}"
  major_engine_version     = "8.0"
  option_group_description = "Terraform OG"

  tags = {
    Name        = "${local.env_prefix.value}-catalogopts"
    Environment = local.env_prefix.value
    }
}
