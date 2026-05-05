# -----------------------------------------------------------------------------
# UC1 RAG Agent — Container App Environment Subnet NSG (TC-3 Bypass Block)
#
# Background: The ALZ provisions the ContainerAppEnvironmentSubnet without an
# NSG attached. UC1 requires that all traffic to the Container App must come
# through APIM (gateway enforcement). This file codifies the NSG that was
# initially created out-of-band (az CLI) to make TC-3 case 3c green.
#
# Rules (lower priority = evaluated first):
#   100 AllowApimInbound     — APIM subnet -> CAE ILB on 80/443
#   110 AllowIntraCAE        — CAE pod-to-pod
#   120 AllowAzureLB         — control-plane health probes
#   150 DenyJumpboxDirect    — explicit block of jumpbox bypass attempts
#   200 DenyVnetIngress      — catch-all VNet ingress block on 80/443
# -----------------------------------------------------------------------------

# --- Subnet lookups (drive rules from live address space, no hard-coding) ---
data "azurerm_virtual_network" "alz" {
  name                = var.alz_vnet_name
  resource_group_name = data.azurerm_resource_group.alz.name
}

data "azurerm_subnet" "cae" {
  name                 = "ContainerAppEnvironmentSubnet"
  virtual_network_name = data.azurerm_virtual_network.alz.name
  resource_group_name  = data.azurerm_resource_group.alz.name
}

data "azurerm_subnet" "apim" {
  name                 = "APIMSubnet"
  virtual_network_name = data.azurerm_virtual_network.alz.name
  resource_group_name  = data.azurerm_resource_group.alz.name
}

data "azurerm_subnet" "jumpbox" {
  name                 = "JumpboxSubnet"
  virtual_network_name = data.azurerm_virtual_network.alz.name
  resource_group_name  = data.azurerm_resource_group.alz.name
}

# --- NSG ---
resource "azurerm_network_security_group" "cae" {
  name                = "ai-alz-cae-nsg"
  location            = var.location
  resource_group_name = data.azurerm_resource_group.alz.name
  tags                = var.tags

  security_rule {
    name                       = "AllowApimInbound"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    source_address_prefix      = data.azurerm_subnet.apim.address_prefixes[0]
    destination_port_ranges    = ["80", "443"]
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "AllowIntraCAE"
    priority                   = 110
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "*"
    source_port_range          = "*"
    source_address_prefix      = data.azurerm_subnet.cae.address_prefixes[0]
    destination_port_range     = "*"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "AllowAzureLB"
    priority                   = 120
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "*"
    source_port_range          = "*"
    source_address_prefix      = "AzureLoadBalancer"
    destination_port_range     = "*"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "DenyJumpboxDirect"
    priority                   = 150
    direction                  = "Inbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    source_address_prefix      = data.azurerm_subnet.jumpbox.address_prefixes[0]
    destination_port_range     = "*"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "DenyVnetIngress"
    priority                   = 200
    direction                  = "Inbound"
    access                     = "Deny"
    protocol                   = "Tcp"
    source_port_range          = "*"
    source_address_prefix      = "VirtualNetwork"
    destination_port_ranges    = ["80", "443"]
    destination_address_prefix = "*"
  }
}

# --- Attach NSG to CAE subnet ---
resource "azurerm_subnet_network_security_group_association" "cae" {
  subnet_id                 = data.azurerm_subnet.cae.id
  network_security_group_id = azurerm_network_security_group.cae.id
}
