output "jenkins_ci_user_arn" {
  value       = aws_iam_user.jenkins_ci.arn
  description = "ARN of the IAM user Jenkins authenticates as (access key created out-of-band, stored in Jenkins' credential store -- see the README)."
}

output "jenkins_ci_user_name" {
  value       = aws_iam_user.jenkins_ci.name
  description = "Name of the Jenkins CI IAM user, for `aws iam create-access-key --user-name`."
}

output "storage_integration_role_arn" {
  value       = aws_iam_role.storage_integration.arn
  description = "ARN passed to Snowflake as storage_aws_role_arn when creating the storage integration."
}
