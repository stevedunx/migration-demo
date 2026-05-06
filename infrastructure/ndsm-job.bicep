@description('Name of the Container Apps environment to create.')
param environmentName string = 'ndsm-env'

@description('Name of the Container Apps job.')
param jobName string = 'ndsm-creator'

@description('Azure region to deploy resources into.')
param location string = resourceGroup().location

@description('Container image to run, e.g. myregistry.azurecr.io/ndsm-creator:latest')
param containerImage string

@description('Name of an existing storage account whose connection string will be passed to the job.')
param storageAccountName string = 'height-store-demo'

@description('10k BNG tile reference to process, passed as the TILE_10K environment variable.')
param tile10k string

@description('CPU cores allocated to each job replica.')
param cpu string = '1.0'

@description('Memory allocated to each job replica.')
param memory string = '2Gi'

// ---------------------------------------------------------------------------
// Log Analytics workspace (required by Container Apps environment)
// ---------------------------------------------------------------------------

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${environmentName}-logs'
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// ---------------------------------------------------------------------------
// Container Apps managed environment
// ---------------------------------------------------------------------------

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: environmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Storage account reference (must already exist)
// ---------------------------------------------------------------------------

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

// ---------------------------------------------------------------------------
// Container Apps job
// ---------------------------------------------------------------------------

resource ndsmJob 'Microsoft.App/jobs@2024-03-01' = {
  name: jobName
  location: location
  properties: {
    environmentId: environment.id
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: 1800
      replicaRetryLimit: 2
    }
    template: {
      containers: [
        {
          name: 'ndsm-creator'
          image: containerImage
          resources: {
            cpu: json(cpu)
            memory: memory
          }
          args: [
            tile10k
          ]
          env: [
              name: 'STORAGE_ACCOUNT_URL'
              value: 'https://${storageAccountName}.blob.core.windows.net'
            }
            {
              name: 'AZURE_STORAGE_CONNECTION_STRING'
              value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccountName};AccountKey=${storageAccount.listKeys().keys[0].value};EndpointSuffix=core.windows.net'
            }
          ]
        }
      ]
    }
  }
}

output jobName string = ndsmJob.name
output environmentId string = environment.id
