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
var deploymentContainerName = 'function-releases'
var blobContainers = [
  deploymentContainerName
  'source-uploads'
  'cert-templates'
  'issued-certs'
]
var githubOidcSubject = 'repo:${githubRepository}:ref:refs/heads/${githubBranch}'
var tags = {
  environment: 'production'
  managedBy: 'codex'
  system: 'ipg-certificate'
}
var roleDefinitionIds = {
  storageBlobDataOwner: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b')
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
    functionAppConfig: {
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
    }
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
      ]
    }
  }
}

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

output functionAppName string = functionApp.name
output functionAppHostName string = functionApp.properties.defaultHostName
output storageAccountName string = storageAccount.name
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
