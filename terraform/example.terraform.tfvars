# Required
tenancy_ocid          = ""
user_ocid             = ""
fingerprint           = ""
private_key_path      = ""
region                = ""
ssh_public_keys       = [
    "ssh-public-key"  # at least 1 ssh public key required
]

# Optional
instance_name         = ""  # defaults to instance-YYYY-MM-DD-hhmm
vcn_display_name      = ""  # defaults to instance_name-vcn
vcn_cidr_block        = ""  # defaults to 10.0.0.0/16
subnet_display_name   = ""  # defaults to instance_name-subnet
subnet_cidr_block     = ""  # defaults to 10.0.0.0/24
internet_gateway_name = ""  # defaults to instance_name-internet-gateway
memory_in_gbs         = 0   # defaults to 24
cpu_count             = 0   # defaults to 4
availability_domain   = ""  # defaults to cycling through availability domains given to --availability-domains