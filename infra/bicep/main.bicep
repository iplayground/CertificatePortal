targetScope = 'resourceGroup'

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Globally unique Azure Functions app name.')
@minLength(2)
@maxLength(60)
param functionAppName string

@description('GitHub repository in owner/name form.')
param githubRepository string = 'iplayground/CertificatePortal'

@description('GitHub branch allowed to deploy through OIDC.')
param githubBranch string = 'main'

@description('Python runtime version for the Flex Consumption app.')
param pythonVersion string = '3.13'

@description('Google OAuth client ID for the portal login flow.')
param portalGoogleClientId string = ''

@description('Google OAuth client secret for the portal login flow.')
@secure()
param portalGoogleClientSecret string = ''

@description('Optional absolute redirect URI override for the portal Google OAuth callback.')
param portalGoogleRedirectUri string = ''

@description('Comma-separated Google Group keys allowed to access the portal.')
@secure()
param portalGoogleAllowedGroupKeys string = ''

@description('Dedicated HMAC secret for public tax receipt download tickets.')
@secure()
param taxReceiptDownloadTicketSecret string = ''

@description('Tax receipt download ticket lifetime in seconds.')
@minValue(1)
param taxReceiptDownloadTicketMaxAgeSeconds int = 600

@description('Optional globally unique Azure Cosmos DB account name. Leave empty to derive one from the Function App name.')
@maxLength(44)
param cosmosAccountName string = ''

@description('Azure Cosmos DB SQL database name. Containers are intentionally defined later with their partition keys.')
param cosmosDatabaseName string = 'ipg-certificate'

@description('Cosmos DB container name for activity management events.')
param cosmosEventsContainerName string = 'events'

@description('Cosmos DB container name for completion certificate records.')
param cosmosCompletionCertsContainerName string = 'completionCerts'

@description('Cosmos DB container name for completion certificate requests.')
param cosmosCompletionCertRequestsContainerName string = 'completionCertRequests'

@description('Cosmos DB container name for tax receipt records.')
param cosmosTaxReceiptsContainerName string = 'taxReceipts'

@description('Cosmos DB container name for public document lookup attempt tracking.')
param cosmosPublicLookupAttemptsContainerName string = 'publicLookupAttempts'

@description('Optional Microsoft Entra security group object IDs that should be able to inspect Cosmos DB data in Azure Portal. Avoid assigning individual users.')
param cosmosPortalDataReaderPrincipalIds array = []

@description('Maximum Flex Consumption instances.')
@minValue(1)
@maxValue(1000)
param maximumInstanceCount int = 100

@description('Memory size per Flex Consumption instance.')
@allowed([
  512
  2048
  4096
])
param instanceMemoryMB int = 2048

var normalizedFunctionAppName = toLower(functionAppName)
var storageAccountName = take('st${take(replace(normalizedFunctionAppName, '-', ''), 9)}${uniqueString(resourceGroup().id, functionAppName)}', 24)
var functionPlanName = '${normalizedFunctionAppName}-fc'
var applicationInsightsName = '${normalizedFunctionAppName}-appi'
var logAnalyticsWorkspaceName = take('${normalizedFunctionAppName}-law', 63)
var githubIdentityName = '${normalizedFunctionAppName}-gh-oidc'
var effectiveCosmosAccountName = empty(cosmosAccountName) ? take('cosmos-${take(replace(normalizedFunctionAppName, '-', ''), 20)}-${uniqueString(resourceGroup().id, functionAppName)}', 44) : toLower(cosmosAccountName)
var deploymentContainerName = 'function-releases'
var documentAssetsContainerName = 'document-assets'
var issuedCertsContainerName = 'issued-certs'
var taxReceiptsContainerName = 'tax-receipts'
var blobContainers = [
  deploymentContainerName
  documentAssetsContainerName
  issuedCertsContainerName
  taxReceiptsContainerName
]
var githubOidcSubject = 'repo:${githubRepository}:ref:refs/heads/${githubBranch}'
var tags = {
  app: 'certificate'
  managedBy: 'codex'
}
var roleDefinitionIds = {
  storageBlobDataOwner: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b')
  storageBlobDataReader: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1')
  storageQueueDataContributor: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '974c5e8b-45b9-4653-ba55-5f855dd0fb88')
  storageTableDataContributor: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3')
  websiteContributor: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'de139f84-1756-47ae-9be6-808fbbe84772')
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    allowBlobPublicAccess: false
    allowCrossTenantReplication: false
    defaultToOAuthAuthentication: true
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2024-01-01' = {
  name: 'default'
  parent: storageAccount
}

resource blobContainersResource 'Microsoft.Storage/storageAccounts/blobServices/containers@2024-01-01' = [for containerName in blobContainers: {
  name: containerName
  parent: blobService
  properties: {
    publicAccess: 'None'
  }
}]

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsWorkspaceName
  location: location
  tags: tags
  properties: {
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
    retentionInDays: 30
    sku: {
      name: 'PerGB2018'
    }
    workspaceCapping: {
      dailyQuotaGb: -1
    }
  }
}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: applicationInsightsName
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalyticsWorkspace.id
  }
}

resource hostingPlan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: functionPlanName
  location: location
  tags: tags
  kind: 'functionapp'
  sku: {
    name: 'FC1'
    tier: 'FlexConsumption'
  }
  properties: {
    reserved: true
  }
}

resource githubDeploymentIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: githubIdentityName
  location: location
  tags: tags
}

resource githubFederatedCredential 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: githubDeploymentIdentity
  name: 'github-main'
  properties: {
    audiences: [
      'api://AzureADTokenExchange'
    ]
    issuer: 'https://token.actions.githubusercontent.com'
    subject: githubOidcSubject
  }
}

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: effectiveCosmosAccountName
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    backupPolicy: {
      type: 'Periodic'
      periodicModeProperties: {
        backupIntervalInMinutes: 240
        backupRetentionIntervalInHours: 8
      }
    }
    capabilities: [
      {
        name: 'EnableServerless'
      }
    ]
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    databaseAccountOfferType: 'Standard'
    disableLocalAuth: true
    enableAutomaticFailover: true
    minimalTlsVersion: 'Tls12'
    locations: [
      {
        failoverPriority: 0
        isZoneRedundant: false
        locationName: location
      }
    ]
    publicNetworkAccess: 'Enabled'
  }
}

resource cosmosSqlDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = {
  name: cosmosDatabaseName
  parent: cosmosAccount
  properties: {
    resource: {
      id: cosmosDatabaseName
    }
  }
}

resource cosmosEventsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  name: cosmosEventsContainerName
  parent: cosmosSqlDatabase
  properties: {
    resource: {
      id: cosmosEventsContainerName
      partitionKey: {
        kind: 'Hash'
        paths: [
          '/id'
        ]
      }
    }
  }
}

resource cosmosCompletionCertsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  name: cosmosCompletionCertsContainerName
  parent: cosmosSqlDatabase
  properties: {
    resource: {
      id: cosmosCompletionCertsContainerName
      partitionKey: {
        kind: 'Hash'
        paths: [
          '/eventId'
        ]
      }
    }
  }
}

resource cosmosCompletionCertRequestsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  name: cosmosCompletionCertRequestsContainerName
  parent: cosmosSqlDatabase
  properties: {
    resource: {
      id: cosmosCompletionCertRequestsContainerName
      partitionKey: {
        kind: 'Hash'
        paths: [
          '/eventId'
        ]
      }
    }
  }
}

resource cosmosTaxReceiptsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  name: cosmosTaxReceiptsContainerName
  parent: cosmosSqlDatabase
  properties: {
    resource: {
      id: cosmosTaxReceiptsContainerName
      partitionKey: {
        kind: 'Hash'
        paths: [
          '/eventId'
        ]
      }
    }
  }
}

resource cosmosPublicLookupAttemptsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  name: cosmosPublicLookupAttemptsContainerName
  parent: cosmosSqlDatabase
  properties: {
    resource: {
      id: cosmosPublicLookupAttemptsContainerName
      partitionKey: {
        kind: 'Hash'
        paths: [
          '/id'
        ]
      }
    }
  }
}

resource functionApp 'Microsoft.Web/sites@2024-04-01' = {
  name: normalizedFunctionAppName
  location: location
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'
  }
  tags: tags
  properties: {
    serverFarmId: hostingPlan.id
    httpsOnly: true
    functionAppConfig: union(
      {
        deployment: {
          storage: {
            type: 'blobContainer'
            value: '${storageAccount.properties.primaryEndpoints.blob}${deploymentContainerName}'
            authentication: {
              type: 'SystemAssignedIdentity'
            }
          }
        }
        runtime: {
          name: 'python'
          version: pythonVersion
        }
        scaleAndConcurrency: {
          instanceMemoryMB: instanceMemoryMB
          maximumInstanceCount: maximumInstanceCount
        }
      },
      {
        siteUpdateStrategy: {
          type: 'RollingUpdate'
        }
      }
    )
    siteConfig: {
      alwaysOn: false
      appSettings: [
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: applicationInsights.properties.ConnectionString
        }
        {
          name: 'AzureWebJobsStorage__accountName'
          value: storageAccount.name
        }
        {
          name: 'AzureWebJobsDisableHomepage'
          value: 'true'
        }
        {
          name: 'COSMOS_ENDPOINT'
          value: cosmosAccount.properties.documentEndpoint
        }
        {
          name: 'COSMOS_DATABASE_NAME'
          value: cosmosSqlDatabase.name
        }
        {
          name: 'COSMOS_EVENTS_CONTAINER'
          value: cosmosEventsContainer.name
        }
        {
          name: 'COSMOS_COMPLETION_CERTS_CONTAINER'
          value: cosmosCompletionCertsContainer.name
        }
        {
          name: 'COSMOS_COMPLETION_CERT_REQUESTS_CONTAINER'
          value: cosmosCompletionCertRequestsContainer.name
        }
        {
          name: 'COSMOS_TAX_RECEIPTS_CONTAINER'
          value: cosmosTaxReceiptsContainer.name
        }
        {
          name: 'COSMOS_PUBLIC_LOOKUP_ATTEMPTS_CONTAINER'
          value: cosmosPublicLookupAttemptsContainer.name
        }
        {
          name: 'BLOB_DOCUMENT_ASSETS_CONTAINER'
          value: documentAssetsContainerName
        }
        {
          name: 'BLOB_ISSUED_CERT_CONTAINER'
          value: issuedCertsContainerName
        }
        {
          name: 'BLOB_TAX_RECEIPTS_CONTAINER'
          value: taxReceiptsContainerName
        }
        {
          name: 'PORTAL_GOOGLE_CLIENT_ID'
          value: portalGoogleClientId
        }
        {
          name: 'PORTAL_GOOGLE_CLIENT_SECRET'
          value: portalGoogleClientSecret
        }
        {
          name: 'PORTAL_GOOGLE_REDIRECT_URI'
          value: portalGoogleRedirectUri
        }
        {
          name: 'PORTAL_GOOGLE_ALLOWED_GROUP_KEYS'
          value: portalGoogleAllowedGroupKeys
        }
        {
          name: 'TAX_RECEIPT_DOWNLOAD_TICKET_SECRET'
          value: taxReceiptDownloadTicketSecret
        }
        {
          name: 'TAX_RECEIPT_DOWNLOAD_TICKET_MAX_AGE_SECONDS'
          value: string(taxReceiptDownloadTicketMaxAgeSeconds)
        }
      ]
    }
  }
}

resource functionCosmosDataContributorRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = {
  name: guid(cosmosAccount.id, functionApp.id, cosmosSqlDatabase.id, 'cosmos-data-contributor')
  parent: cosmosAccount
  properties: {
    principalId: functionApp.identity.principalId
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
    scope: '${cosmosAccount.id}/dbs/${cosmosSqlDatabase.name}'
  }
}

resource cosmosPortalDataReaderRoleAssignments 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = [for principalId in cosmosPortalDataReaderPrincipalIds: {
  name: guid(cosmosAccount.id, principalId, 'cosmos-data-reader')
  parent: cosmosAccount
  properties: {
    principalId: principalId
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000001'
    scope: cosmosAccount.id
  }
}]

resource functionStorageBlobRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, functionApp.id, roleDefinitionIds.storageBlobDataOwner)
  scope: storageAccount
  properties: {
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: roleDefinitionIds.storageBlobDataOwner
  }
}

resource functionStorageQueueRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, functionApp.id, roleDefinitionIds.storageQueueDataContributor)
  scope: storageAccount
  properties: {
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: roleDefinitionIds.storageQueueDataContributor
  }
}

resource functionStorageTableRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, functionApp.id, roleDefinitionIds.storageTableDataContributor)
  scope: storageAccount
  properties: {
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: roleDefinitionIds.storageTableDataContributor
  }
}

resource githubWebsiteContributorRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(functionApp.id, githubDeploymentIdentity.id, roleDefinitionIds.websiteContributor)
  scope: functionApp
  properties: {
    principalId: githubDeploymentIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: roleDefinitionIds.websiteContributor
  }
}

resource githubStorageBlobReaderRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, githubDeploymentIdentity.id, roleDefinitionIds.storageBlobDataReader)
  scope: storageAccount
  properties: {
    principalId: githubDeploymentIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: roleDefinitionIds.storageBlobDataReader
  }
}

output functionAppName string = functionApp.name
output functionAppHostName string = functionApp.properties.defaultHostName
output storageAccountName string = storageAccount.name
output cosmosAccountName string = cosmosAccount.name
output cosmosDatabaseName string = cosmosSqlDatabase.name
output cosmosEndpoint string = cosmosAccount.properties.documentEndpoint
output cosmosEventsContainerName string = cosmosEventsContainer.name
output cosmosCompletionCertsContainerName string = cosmosCompletionCertsContainer.name
output cosmosCompletionCertRequestsContainerName string = cosmosCompletionCertRequestsContainer.name
output cosmosTaxReceiptsContainerName string = cosmosTaxReceiptsContainer.name
output cosmosPublicLookupAttemptsContainerName string = cosmosPublicLookupAttemptsContainer.name
output deploymentContainerName string = deploymentContainerName
output deploymentContainerUrl string = '${storageAccount.properties.primaryEndpoints.blob}${deploymentContainerName}'
output githubActionsIdentityClientId string = githubDeploymentIdentity.properties.clientId
output githubActionsIdentityPrincipalId string = githubDeploymentIdentity.properties.principalId
output githubActionsIdentityResourceId string = githubDeploymentIdentity.id
output githubOidcSubject string = githubOidcSubject
output githubRepository string = githubRepository
output githubBranch string = githubBranch
output applicationInsightsConnectionString string = applicationInsights.properties.ConnectionString
output tenantId string = tenant().tenantId
output subscriptionId string = subscription().subscriptionId
