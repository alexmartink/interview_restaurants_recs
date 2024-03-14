terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">=2.0"
    }
  }
}

provider "azurerm" {
  features {}
}

resource "azurerm_resource_group" "restaurant_rec" {
  name     = "restaurant-recommendation-app"
  location = "East US"
}

resource "azurerm_cosmosdb_account" "restaurant_rec_cosmosdb_acc" {
  name                = "restaurant-recommendation-cosmosdb"
  location            = azurerm_resource_group.restaurant_rec.location
  resource_group_name = azurerm_resource_group.restaurant_rec.name
  offer_type          = "Standard"
  consistency_policy {
    consistency_level       = "BoundedStaleness"
    max_interval_in_seconds = 300
    max_staleness_prefix    = 100000
  }

  geo_location {
    location          = "eastus"
    failover_priority = 1
  }

  geo_location {
    location          = "westus"
    failover_priority = 0
  }
}

resource "azurerm_cosmosdb_sql_database" "restaurant_rec_cosmosdb" {
  name                = "RestaurantDatabase"
  resource_group_name = azurerm_cosmosdb_account.restaurant_rec_cosmosdb_acc.resource_group_name
  account_name        = azurerm_cosmosdb_account.restaurant_rec_cosmosdb_acc.name
  throughput          = 400
}

resource "azurerm_cosmosdb_sql_container" "restaurant_rec_cosmosdb_container" {
  name                = "RestaurantContainer"
  resource_group_name = azurerm_cosmosdb_account.restaurant_rec_cosmosdb.resource_group_name
  account_name        = azurerm_cosmosdb_account.restaurant_rec_cosmosdb.name
  database_name       = azurerm_cosmosdb_sql_database.restaurant_rec_cosmosdb.name
  partition_key_path  = "/style"
  throughput          = 400
}

resource "azurerm_cosmosdb_sql_container" "request_log" {
  name                = "RequestLogContainer"
  resource_group_name = azurerm_cosmosdb_account.restaurant_rec_cosmosdb_acc.resource_group_name
  account_name        = azurerm_cosmosdb_account.restaurant_rec_cosmosdb_acc.name
  database_name       = azurerm_cosmosdb_sql_database.restaurant_rec_cosmosdb.name
  partition_key_path  = "/endpoint"
  throughput          = 400
}

resource "azuread_application_registration" "example" {
  display_name = "example"
}

resource "random_uuid" "example_administrator" {}

resource "azuread_application" "restaurant_recommendation_app" {
  display_name                       = "restaurant-recommendation-app"
  implicit_grant {
    access_token_issuance_enabled = true
  }
}

resource "azuread_service_principal" "restaurant_rec_service_principle" {
  application_id = azuread_application.restaurant_recommendation_app.application_id
}

resource "azurerm_role_assignment" "restaurant_rec_role_assignment" {
  application_id       = azuread_application.restaurant_recommendation_app.id
  scope                = azurerm_cosmosdb_account.restaurant_rec_cosmosdb_acc.id
  role_definition_name = "Cosmos DB Account Contributor"
  principal_id         = azuread_service_principal.restaurant_rec_service_principle.id
}

resource "azuread_application_app_role" "restaurant_creator" {
  application_id = azuread_application.restaurant_recommendation_app.id
  allowed_member_types  = ["User"]
  description           = "Allows creation of restaurants in Cosmos DB"
  display_name          = "Restaurant Creator"
  value                 = "RestaurantCreator"
}

resource "azuread_application_app_role" "request_log_viewer" {
  application_id = azuread_application.restaurant_recommendation_app.id
  allowed_member_types  = ["User"]
  description           = "Allows viewing of request logs"
  display_name          = "Request Log Viewer"
  value                 = "RequestLogViewer"
}

resource "azurerm_service_plan" "restaurant_rec_app_svc_plan" {
  name                = "restaurant-rec-app-svc-plan"
  location            = "East US"
  resource_group_name = azurerm_resource_group.restaurant_rec.name
  kind                = "Linux"
  reserved            = true

  sku {
    tier = "Standard"
    size = "S1"
  }
}

resource "azurerm_app_service" "restaurant_rec_app_svc" {
  name                = "restaurant-rec-app-svc"
  location            = "East US"
  resource_group_name = azurerm_resource_group.restaurant_rec.name
  app_service_plan_id = azurerm_app_service_plan.restaurant_rec_app_svc_plan.id

  site_config {
    linux_fx_version = "PYTHON|3.8"
  }

  app_settings = {
    "WEBSITE_RUN_FROM_PACKAGE" = "https://github.com/alexmartink/test_api/archive/refs/heads/main.zip"  # Replace with your GitHub repo URL
    "PYTHON_VERSION"           = "3.8"
    "COSMOSDB_ENDPOINT"        = azurerm_cosmosdb_account.restaurant_rec_cosmosdb_acc.endpoint
    "COSMOSDB_KEY"             = azurerm_cosmosdb_account.restaurant_rec_cosmosdb_acc.primary_master_key
    "AZURE_AD_TENANT_ID"       = var.azure_ad_tenant_id
    "AZURE_AD_CLIENT_ID"       = var.azure_ad_client_id
  }

  lifecycle {
    ignore_changes = [app_settings]
  }

  identity {
    type = "SystemAssigned"
  }

  provisioner "remote-exec" {
    inline = [
      "cd /home/site/wwwroot",
      "python -m pip install -r requirements.txt"
    ]

    connection {
      type        = "ssh"
      host        = azurerm_app_service.restaurant_rec_app_svc.default_site_hostname
      user        = "${azurerm_app_service.restaurant_rec_app_svc.git_remote_repository_username}"
      private_key = tls_private_key.example.private_key_pem  # Use the generated private key
    }
  }
}

resource "tls_private_key" "example" {
  algorithm   = "RSA"
  rsa_bits    = 4096
}