# Every test uses a mocked AWS provider. No AWS endpoint or credentials are used.
mock_provider "aws" {
  mock_data "aws_caller_identity" {
    defaults = { account_id = "123456789012" }
  }
}

run "disabled_state" {
  command = plan
  assert {
    condition     = length(aws_s3_bucket.state) == 0
    error_message = "State bootstrap must default disabled."
  }
}
variables {
  bucket_name              = "opsproof-offline-test-state"
  expected_account_id      = "123456789012"
  approval_reference       = "OFFLINE_FIXTURE_ONLY"
  approval_acknowledgement = "I_APPROVE_TEMPORARY_OPSPROOF_AWS_CHARGES"
}
run "private_versioned_state" {
  command = plan
  variables { enable_paid_resources = true }
  assert {
    condition     = aws_s3_bucket_public_access_block.state[0].block_public_acls && aws_s3_bucket_public_access_block.state[0].block_public_policy && aws_s3_bucket_public_access_block.state[0].restrict_public_buckets
    error_message = "State must block public access."
  }
  assert {
    condition     = aws_s3_bucket_versioning.state[0].versioning_configuration[0].status == "Enabled"
    error_message = "State must be versioned."
  }
}
run "reject_foreign_account" {
  command = plan
  variables {
    enable_paid_resources = true
    expected_account_id   = "000000000000"
  }
  expect_failures = [aws_s3_bucket.state]
}
