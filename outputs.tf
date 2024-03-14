output "azure_role_id_restaurant_creator" {
  value = azuread_application_app_role.restaurant_creator.id
}

output "azure_role_id_request_viewer" {
  value = azuread_application_app_role.request_log_viewer.id
}


output "cosmosdb_endpoint" {
  value = azurerm_cosmosdb_account.restaurant_rec_cosmosdb_acc.endpoint
}

output "cosmosdb_key" {
  value = azurerm_cosmosdb_account.restaurant_rec_cosmosdb_acc.primary_key
}

output "azure_ad_tenant_id" {
  value = var.azure_ad_tenant_id
}