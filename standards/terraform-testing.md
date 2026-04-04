# Terraform Testing

Terraform's built-in testing framework validates that configuration updates do not introduce breaking changes. Tests execute against temporary resources, protecting existing infrastructure and state files.

## File Structure

Test files use `.tftest.hcl` extension. Organize in a `tests/` directory with naming that distinguishes unit from integration tests:

```
my-module/
  main.tf
  variables.tf
  outputs.tf
  tests/
    validation_unit_test.tftest.hcl
    edge_cases_unit_test.tftest.hcl
    full_stack_integration_test.tftest.hcl
```

## Test Modes

| Mode | Command | Creates resources | Use for |
|------|---------|-------------------|---------|
| Plan | `command = plan` | No | Unit tests: validation rules, variable defaults, conditional logic, resource configuration |
| Apply | `command = apply` | Yes (temporary) | Integration tests: real provisioning, cross-resource dependencies, output values |

Default is `apply`. Always use `plan` for tests that do not need real infrastructure.

## Core Components

### Run Block

Each `run` block is a single test scenario. Run blocks execute sequentially by default.

```hcl
run "test_default_configuration" {
  command = plan

  assert {
    condition     = aws_instance.example.instance_type == "t2.micro"
    error_message = "Instance type must default to t2.micro"
  }
}
```

### Variables

Define at file level (applied to all run blocks) or per run block (overrides file level). Test-level variables take highest precedence over all other sources.

```hcl
variables {
  instance_type = "t2.small"
}

run "test_override" {
  command = plan

  variables {
    instance_type = "t3.large"
  }

  assert {
    condition     = var.instance_type == "t3.large"
    error_message = "Run-level variable must override file-level"
  }
}
```

Variables can reference prior run blocks for chained tests:

```hcl
run "setup_vpc" {
  command = apply
}

run "test_with_vpc" {
  command = plan

  variables {
    vpc_id = run.setup_vpc.vpc_id
  }
}
```

### Assert Block

All assertions in a run block must pass for the test to succeed.

```hcl
assert {
  condition     = <expression>
  error_message = "failure description"
}
```

Assert against resource attributes, output values, data source results, and computed values. Use `length()`, `contains()`, `startswith()`, `can()`, and other Terraform functions in conditions.

### Expect Failures

Validate that specific variables or resources correctly reject invalid input. The test passes when the specified blocks produce an error.

```hcl
run "test_rejects_invalid_cidr" {
  command = plan

  variables {
    vpc_cidr = "invalid-cidr"
  }

  expect_failures = [
    var.vpc_cidr,
  ]
}

run "test_rejects_empty_name" {
  command = plan

  variables {
    name = ""
  }

  expect_failures = [
    var.name,
  ]
}
```

## Mock Providers (Terraform 1.7+)

Simulate provider behavior without creating real infrastructure. Use for unit tests that need provider responses.

```hcl
mock_provider "aws" {
  mock_data "aws_ami" {
    defaults = {
      id = "ami-mock12345"
    }
  }
}

run "test_with_mock_ami" {
  command = plan

  providers = {
    aws = aws
  }

  assert {
    condition     = aws_instance.example.ami == "ami-mock12345"
    error_message = "Instance must use the mock AMI"
  }
}
```

## Parallel Execution (Terraform 1.9+)

Enable parallel execution for independent run blocks:

```hcl
test {
  parallel = true
}
```

Individual run blocks can override: `parallel = false` for blocks that depend on shared state.

### State Key Isolation

Use `state_key` to isolate state between parallel run blocks that would otherwise conflict:

```hcl
run "test_region_us_east" {
  command  = apply
  parallel = true
  state_key = "us-east"

  variables {
    region = "us-east-1"
  }
}

run "test_region_eu_west" {
  command  = apply
  parallel = true
  state_key = "eu-west"

  variables {
    region = "eu-west-1"
  }
}
```

## Test Patterns

### Validation Testing (Unit)

```hcl
run "test_instance_type_validation" {
  command = plan

  variables {
    instance_type = "t2.nano"
  }

  expect_failures = [
    var.instance_type,
  ]
}
```

### Conditional Resource Creation (Unit)

```hcl
run "test_monitoring_disabled" {
  command = plan

  variables {
    enable_monitoring = false
  }

  assert {
    condition     = length(aws_cloudwatch_alarm.cpu) == 0
    error_message = "No alarms must be created when monitoring is disabled"
  }
}
```

### Output Verification (Integration)

```hcl
run "test_outputs" {
  command = apply

  assert {
    condition     = output.vpc_id != ""
    error_message = "VPC ID output must not be empty"
  }

  assert {
    condition     = can(regex("^vpc-", output.vpc_id))
    error_message = "VPC ID must start with vpc-"
  }
}
```

### Multi-Step Provisioning (Integration)

```hcl
run "create_network" {
  command = apply

  assert {
    condition     = aws_vpc.main.id != ""
    error_message = "VPC must be created"
  }
}

run "create_compute" {
  command = apply

  variables {
    vpc_id = run.create_network.vpc_id
  }

  assert {
    condition     = aws_instance.app.subnet_id != ""
    error_message = "Instance must be placed in a subnet"
  }
}
```

## Running Tests

```bash
# Run all tests
terraform test

# Run specific test file
terraform test -filter=tests/validation_unit_test.tftest.hcl

# Verbose output
terraform test -verbose
```

## Rules

- Every module must have at least one unit test (plan mode) for variable validation
- Every variable with a `validation` block must have a corresponding `expect_failures` test
- Integration tests (apply mode) must clean up after themselves. Terraform test does this automatically, but verify with `terraform state list` after test failures
- Use mock providers for unit tests whenever possible. Reserve apply-mode tests for behaviors that require real infrastructure responses
- Name test files descriptively: `validation_unit_test.tftest.hcl`, not `test1.tftest.hcl`
- Test conditional resource creation for every `count` or `for_each` that depends on a variable

## Related Standards

- `standards/infrastructure.md`: Infrastructure
