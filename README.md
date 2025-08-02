# OCI Always Free Infrastructure

Automated Oracle Cloud Infrastructure (OCI) deployment for always-free tier resources with intelligent retry logic to handle capacity constraints.

## Features

- **Always-Free Tier Resources**: ARM-based VM.Standard.A1.Flex instance (4 OCPUs, 24GB RAM)
- **Automatic OS Selection**: Dynamically selects the latest Oracle Linux 9 image
- **Intelligent Retry Logic**: Python script handles "Out of host capacity" errors by cycling through availability domains
- **Flexible Configuration**: Comprehensive Terraform variables for customization
- **SSH Key Validation**: Ensures at least one SSH public key is provided
- **Resource Cleanup**: Automatic cleanup on failures to avoid resource waste

## Infrastructure Components

- **Compute Instance**: VM.Standard.A1.Flex with Oracle Linux 9
- **Virtual Cloud Network (VCN)**: Configurable CIDR blocks
- **Subnet**: Subnet with public IP assignment for internet connectivity
- **Internet Gateway**: Provides internet connectivity
- **Security**: SSH access with configurable public keys

## Prerequisites

### OCI Account Setup

1. Create an OCI account and set up the always-free tier
2. Create an API key pair for programmatic access
3. Note your tenancy OCID, user OCID, and API key fingerprint
4. Identify available regions and availability domains

> **Tip**: Switching to Pay As You Go (PAYG) billing gives you capacity priority over free-tier accounts. You'll still pay nothing if you stay within always-free limits, but get better resource availability during high-demand periods.

### Local Dependencies

- **Terraform** >= 1.0
- **Python** >= 3.12

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/LeetCyberSecurity/oci-always-free.git
cd oci-always-free
```

### 2. Configure Authentication

Copy and customize the Terraform variables:

```bash
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
```

Edit `terraform/terraform.tfvars` with your OCI credentials:

```hcl
# Required
tenancy_ocid     = "ocid1.tenancy.oc1..aaaaaaaa..."
user_ocid        = "ocid1.user.oc1..aaaaaaaa..."
fingerprint      = "aa:bb:cc:dd:ee:ff:gg:11:22:33:44:55:66:77:88:99"
private_key_path = "path/to/your/oci_private_key.pem"
region           = "my-region"
instance_name    = "my-server"
ssh_public_keys  = [
    "ssh-rsa ABCDEFG123456789... user@host"
]
```

### 3. Initialize Terraform

```bash
cd terraform
terraform init
```

### 4. Deploy with Retry Logic

Use the Python script for automatic retry handling:

```bash
python3 oci.py terraform/ \
    --availability-domains \
    "your-tenancy-prefix:AD-1" \
    "your-tenancy-prefix:AD-2" \
    "your-tenancy-prefix:AD-3"
```

Or deploy directly with Terraform:

```bash
cd terraform
terraform plan
terraform apply
```

## Configuration Options

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `tenancy_ocid` | Your OCI tenancy OCID | `ocid1.tenancy.oc1..aaaaaaaa...` |
| `user_ocid` | Your OCI user OCID | `ocid1.user.oc1..aaaaaaaa...` |
| `fingerprint` | API key fingerprint | `aa:bb:cc:dd:ee:ff:gg:11:22:33:44:55:66:77:88:99` |
| `private_key_path` | Path to your private key | `~/.oci/oci_api_key.pem` |
| `region` | OCI region | `my-region` |
| `instance_name` | Name for your instance | `my-server` |
| `ssh_public_keys` | List of SSH public keys | `["ssh-rsa ABCDEFG..."]` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `vcn_display_name` | VCN display name | `{instance_name}-vcn` |
| `vcn_cidr_block` | VCN CIDR block | `10.0.0.0/16` |
| `subnet_display_name` | Subnet display name | `{instance_name}-subnet` |
| `subnet_cidr_block` | Subnet CIDR block | `10.0.0.0/24` |
| `internet_gateway_name` | Internet gateway name | `{instance_name}-internet-gateway` |
| `memory_in_gbs` | Instance memory in GB | `24` |
| `cpu_count` | Number of OCPUs | `4` |

## Python Retry Script

The `oci.py` script provides intelligent retry logic for OCI capacity issues:

### Features

- **Automatic Availability Domain Cycling**: Tries different ADs when capacity is unavailable
- **Resource Cleanup**: Destroys failed deployments automatically
- **Comprehensive Logging**: Logs all attempts with timestamps
- **Configurable Retry Logic**: Customizable attempts and delays

### Usage

```bash
python3 oci.py [CONFIG_DIR] [OPTIONS]
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--max-attempts` | Maximum retry attempts | 50 |
| `--retry-delay` | Delay between retries (seconds) | 30 |
| `--availability-domains` | List of ADs to cycle through | Required |
| `--no-auto-approve` | Disable auto-approval | Auto-approve enabled |
| `--log-file` | Log file name | `terraform_retry.log` |

### Example

```bash
python3 oci.py terraform/ \
    --max-attempts 10 \
    --retry-delay 60 \
    --availability-domains \
    "abcd:AD-1" \
    "abcd:AD-2" \
    "abcd:AD-3"
```

## Troubleshooting

### Common Issues

1. **"Out of host capacity"**
   - Use the Python retry script with multiple availability domains
   - Try different regions if all ADs in one region are full

2. **"Service limit exceeded"**
   - Check your OCI service limits in the console
   - Ensure you're within always-free tier limits

3. **Authentication errors**
   - Verify your API key is correctly configured
   - Check file permissions on your private key (should be 600)
   - Ensure your user has necessary IAM permissions

4. **SSH connection issues**
   - Verify your public key is correctly formatted
   - Check security groups allow SSH (port 22)
   - Ensure the instance has a public IP

### Getting Help

- Check the logs directory for detailed execution logs
- Review OCI console for resource status
- Verify Terraform state with `terraform show`

## License

This project is licensed under the GPL-3.0 License - see the LICENSE file for details.