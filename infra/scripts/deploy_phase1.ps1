[CmdletBinding()]
param(
    [string]$StackName = "data-automation-phase1",
    [string]$Region = "ap-south-1",
    [string]$EnvironmentName = "dev",
    [string]$JobsTableName = "analytics_jobs",
    [string]$EventsTableName = "analytics_events",
    [string]$RawUploadPrefix = "raw/uploads/",
    [string]$StepFunctionName = "analytics-orchestrator-phase1",
    [string]$TemplatePath = "infra/cloudformation/phase1_event_driven_pipeline.yaml",
    [string]$EnvFilePath = ".env"
)

$ErrorActionPreference = "Stop"

function Set-EnvValue {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Key,
        [Parameter(Mandatory = $true)][string]$Value
    )

    if (-not (Test-Path $Path)) {
        throw "Environment file '$Path' does not exist."
    }

    $lines = Get-Content -Path $Path
    $escapedKey = [regex]::Escape($Key)
    $updated = $false
    $newLines = foreach ($line in $lines) {
        if ($line -match "^$escapedKey=") {
            $updated = $true
            "$Key=$Value"
        } else {
            $line
        }
    }

    if (-not $updated) {
        $newLines += "$Key=$Value"
    }

    Set-Content -Path $Path -Value $newLines
}

Write-Host "Checking AWS CLI..." -ForegroundColor Cyan
aws --version | Out-Null

if (-not (Test-Path $TemplatePath)) {
    throw "Template not found at '$TemplatePath'."
}

if (-not (Test-Path $EnvFilePath)) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" $EnvFilePath
        Write-Host "Created $EnvFilePath from .env.example." -ForegroundColor Yellow
    } else {
        throw "Could not find .env.example to bootstrap $EnvFilePath."
    }
}

Write-Host "Validating AWS credentials..." -ForegroundColor Cyan
aws sts get-caller-identity --region $Region | Out-Null

Write-Host "Deploying Phase 1 stack '$StackName' in region '$Region'..." -ForegroundColor Cyan
aws cloudformation deploy `
    --region $Region `
    --stack-name $StackName `
    --template-file $TemplatePath `
    --capabilities CAPABILITY_NAMED_IAM `
    --parameter-overrides `
        EnvironmentName=$EnvironmentName `
        JobsTableName=$JobsTableName `
        EventsTableName=$EventsTableName `
        RawUploadPrefix=$RawUploadPrefix `
        StepFunctionName=$StepFunctionName | Out-Null

Write-Host "Reading stack outputs..." -ForegroundColor Cyan
$outputsJson = aws cloudformation describe-stacks `
    --region $Region `
    --stack-name $StackName `
    --query "Stacks[0].Outputs" `
    --output json

$outputs = @{}
($outputsJson | ConvertFrom-Json) | ForEach-Object {
    $outputs[$_.OutputKey] = $_.OutputValue
}

if (-not $outputs.ContainsKey("DataBucketName")) {
    throw "Stack output 'DataBucketName' was not found."
}

Set-EnvValue -Path $EnvFilePath -Key "AWS_REGION" -Value $Region
Set-EnvValue -Path $EnvFilePath -Key "S3_BUCKET_DATASETS" -Value $outputs["DataBucketName"]
Set-EnvValue -Path $EnvFilePath -Key "S3_RAW_UPLOAD_PREFIX" -Value $RawUploadPrefix.TrimEnd("/")
Set-EnvValue -Path $EnvFilePath -Key "DYNAMODB_TABLE_JOBS" -Value $outputs["JobsTableName"]
Set-EnvValue -Path $EnvFilePath -Key "DYNAMODB_TABLE_EVENTS" -Value $outputs["EventsTableName"]
Set-EnvValue -Path $EnvFilePath -Key "STEP_FUNCTION_ARN" -Value $outputs["StateMachineArn"]
Set-EnvValue -Path $EnvFilePath -Key "LAMBDA_TRIGGER_NAME" -Value $outputs["S3StarterLambdaName"]
Set-EnvValue -Path $EnvFilePath -Key "PIPELINE_MODE" -Value "aws"
Set-EnvValue -Path $EnvFilePath -Key "PIPELINE_START_MODE" -Value "s3_event"
Set-EnvValue -Path $EnvFilePath -Key "PIPELINE_JOBS_USER_GSI" -Value "gsi_user_created_at"
Set-EnvValue -Path $EnvFilePath -Key "POST_UPLOAD_PAGES_ENABLED" -Value "true"

Write-Host ""
Write-Host "Phase 1 deployment complete." -ForegroundColor Green
Write-Host "S3 bucket:           $($outputs["DataBucketName"])" -ForegroundColor Green
Write-Host "Jobs table:          $($outputs["JobsTableName"])" -ForegroundColor Green
Write-Host "Events table:        $($outputs["EventsTableName"])" -ForegroundColor Green
Write-Host "Step Function ARN:   $($outputs["StateMachineArn"])" -ForegroundColor Green
Write-Host "S3 trigger Lambda:   $($outputs["S3StarterLambdaName"])" -ForegroundColor Green
Write-Host ""
Write-Host "Updated env file:    $EnvFilePath" -ForegroundColor Green
Write-Host "Next: restart Flask app and run one upload test from the UI." -ForegroundColor Cyan
