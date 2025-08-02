provider "oci" {
    tenancy_ocid     = var.tenancy_ocid
    user_ocid        = var.user_ocid
    fingerprint      = var.fingerprint
    private_key_path = var.private_key_path
    region           = var.region
}

locals {
    instance_name = var.instance_name != "" ? var.instance_name : "instance-${formatdate("YYYY-MM-DD-hhmm", timestamp())}"
}

data "oci_core_images" "oracle_linux" {
    compartment_id           = var.tenancy_ocid
    operating_system         = "Oracle Linux"
    operating_system_version = "9"
    shape                    = "VM.Standard.A1.Flex"
    sort_by                  = "TIMECREATED"
    sort_order               = "DESC"
}

resource "oci_core_instance" "generated_oci_core_instance" {
	agent_config {
		is_management_disabled = false
		is_monitoring_disabled = false
		plugins_config {
			desired_state = "DISABLED"
			name = "WebLogic Management Service"
		}
		plugins_config {
			desired_state = "DISABLED"
			name = "Vulnerability Scanning"
		}
		plugins_config {
			desired_state = "DISABLED"
			name = "Oracle Java Management Service"
		}
		plugins_config {
			desired_state = "DISABLED"
			name = "OS Management Hub Agent"
		}
		plugins_config {
			desired_state = "DISABLED"
			name = "Management Agent"
		}
		plugins_config {
			desired_state = "DISABLED"
			name = "Fleet Application Management Service"
		}
		plugins_config {
			desired_state = "ENABLED"
			name = "Custom Logs Monitoring"
		}
		plugins_config {
			desired_state = "DISABLED"
			name = "Compute RDMA GPU Monitoring"
		}
		plugins_config {
			desired_state = "ENABLED"
			name = "Compute Instance Run Command"
		}
		plugins_config {
			desired_state = "ENABLED"
			name = "Compute Instance Monitoring"
		}
		plugins_config {
			desired_state = "DISABLED"
			name = "Compute HPC RDMA Auto-Configuration"
		}
		plugins_config {
			desired_state = "DISABLED"
			name = "Compute HPC RDMA Authentication"
		}
		plugins_config {
			desired_state = "ENABLED"
			name = "Cloud Guard Workload Protection"
		}
		plugins_config {
			desired_state = "DISABLED"
			name = "Block Volume Management"
		}
		plugins_config {
			desired_state = "DISABLED"
			name = "Bastion"
		}
	}
	availability_config {
		recovery_action = "RESTORE_INSTANCE"
	}
	availability_domain = var.availability_domain
	compartment_id = var.tenancy_ocid
	create_vnic_details {
		assign_ipv6ip = false
		assign_private_dns_record = true
		assign_public_ip = true
		subnet_id = "${oci_core_subnet.generated_oci_core_subnet.id}"
	}
	display_name = local.instance_name
	instance_options {
		are_legacy_imds_endpoints_disabled = false
	}
	metadata = {
		"ssh_authorized_keys" = join("\n", var.ssh_public_keys)
	}
	shape = "VM.Standard.A1.Flex"
	shape_config {
		memory_in_gbs = var.memory_in_gbs != 0 ? var.memory_in_gbs : 24
		ocpus = var.cpu_count != 0 ? var.cpu_count : 4
	}
	source_details {
		source_id = data.oci_core_images.oracle_linux.images[0].id
		source_type = "image"
	}
}

resource "oci_core_vcn" "generated_oci_core_vcn" {
	cidr_blocks = [var.vcn_cidr_block != "" ? var.vcn_cidr_block : "10.0.0.0/16"]
	compartment_id = var.tenancy_ocid
	display_name = var.subnet_display_name != "" ? var.subnet_display_name : "${local.instance_name}-vcn"
	dns_label = substr(replace(lower(local.instance_name), "_", "-"), 0, 15)
}

resource "oci_core_internet_gateway" "generated_oci_core_internet_gateway" {
	compartment_id = var.tenancy_ocid
	display_name = var.internet_gateway_name != "" ? var.internet_gateway_name : "${local.instance_name}-internet-gateway"
	vcn_id = oci_core_vcn.generated_oci_core_vcn.id
}

resource "oci_core_default_route_table" "generated_oci_core_default_route_table" {
	manage_default_resource_id = oci_core_vcn.generated_oci_core_vcn.default_route_table_id
	
	route_rules {
		destination = "0.0.0.0/0"
		destination_type = "CIDR_BLOCK"
		network_entity_id = oci_core_internet_gateway.generated_oci_core_internet_gateway.id
	}
}

resource "oci_core_subnet" "generated_oci_core_subnet" {
	cidr_block = var.subnet_cidr_block != "" ? var.subnet_cidr_block : "10.0.0.0/24"
	compartment_id = var.tenancy_ocid
	display_name = var.subnet_display_name != "" ? var.subnet_display_name : "${local.instance_name}-subnet"
	dns_label = substr(replace(lower(local.instance_name), "_", "-"), 0, 15)
	vcn_id = oci_core_vcn.generated_oci_core_vcn.id
}

variable "tenancy_ocid" {
    description = "OCID of the tenancy"
    type        = string
}

variable "user_ocid" {
    description = "OCID of the user"
    type        = string
}

variable "fingerprint" {
    description = "Fingerprint of the API key"
    type        = string
}

variable "private_key_path" {
    description = "Path to the private key file"
    type        = string
}

variable "region" {
    description = "OCI region"
    type        = string
}

variable "instance_name" {
    description = "Instance name"
    type        = string
}

variable "ssh_public_keys" {
    description = "SSH public keys"
    type        = list(string)
    validation {
        condition     = length(var.ssh_public_keys) > 0
        error_message = "At least one SSH public key must be provided."
    }
}

variable "vcn_display_name" {
    description = "VCN display name"
    type        = string
}

variable "vcn_cidr_block" {
    description = "VCN CIDR block"
    type        = string
}

variable "subnet_display_name" {
    description = "Subnet display name"
    type        = string
}

variable "subnet_cidr_block" {
    description = "Subnet CIDR block"
    type        = string
}

variable "internet_gateway_name" {
    description = "Subnet display name"
    type        = string
}

variable "memory_in_gbs" {
    description = "Memory in GBs"
    type        = number
}

variable "cpu_count" {
    description = "CPU count"
    type        = number
}

variable "availability_domain" {
    description = "Availability domain"
    type        = string
}