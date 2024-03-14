# Flask Application with Azure Cosmos DB Integration - Restaurant Recommendations

## Overview

This project consists of a Flask application (`app.py`) that interacts with Azure Cosmos DB for restaurant data storage. Additionally, it includes a CI/CD pipeline (`main.yml`) for automated deployment using GitHub Actions, and Terraform configuration (`main.tf`) for provisioning Azure resources.

## app.py

The `app.py` file contains the Flask application logic. It serves as the backend for managing restaurant data and authorization with Azure AD.

### Functionality:

- **Endpoints:**
  - `/create_roles`: Creates custom roles for managing restaurant data in Azure Cosmos DB.
  - `/restaurants`: Allows creation of restaurants in the Cosmos DB container.
  - `/recommendations`: Retrieves restaurant recommendations based on specified criteria.
  - `/requests`: Retrieves requests made to the application.

- **Authorization:**
  - Implements role-based access control (RBAC) using Azure AD.
  - Requires authentication token in request headers for certain endpoints.

- **Cosmos DB Integration:**
  - Utilizes Azure Cosmos DB Python SDK for database operations.
  - Stores restaurant data in Cosmos DB containers.

## main.yml

The `main.yml` file defines the CI/CD pipeline using GitHub Actions. It automates the deployment process whenever changes are pushed to the repository.

### Pipeline Steps:

1. **Checkout Repository:** Retrieves the latest code from the repository.
4. **Setup Terraform:** Initializes Terraform for Azure resource provisioning.
6. **Terraform Init:** Initializes Terraform for Azure resource provisioning.
7. **Terraform Plan:** Generates an execution plan for Terraform deployment.
8. **Terraform Apply:** Applies the execution plan to provision Azure resources.

## main.tf

The `main.tf` file contains the Terraform configuration for provisioning Azure resources required by the Flask application.

### Resources Provisioned:

- **Azure Cosmos DB Account:** Creates a Cosmos DB account for storing restaurant data.
- **Azure Cosmos DB SQL Database:** Defines the database within the Cosmos DB account.
- **Azure Cosmos DB SQL Containers:** Specifies containers for restaurants and request logs.
- **Azure App Service Plan:** Sets up the service plan for hosting the Flask application.
- **Azure App Service:** Deploys the Flask application to the App Service.

### Environment Variables:

- Defines environment variables required by the Flask application, such as Cosmos DB connection details and Azure AD credentials.