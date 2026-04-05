[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$BucketName,
    [string]$Region = "ap-south-1",
    [string]$Prefix = "code/artifacts"
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$artifactDir = Join-Path $repoRoot "infra\build"
if (Test-Path $artifactDir) {
    Remove-Item -LiteralPath $artifactDir -Recurse -Force
}
New-Item -Path $artifactDir -ItemType Directory | Out-Null

$lambdaFiles = @(
    "s3_start_execution.py",
    "update_job_status.py",
    "handle_failure.py",
    "load_glue_summary.py",
    "decision_engine.py",
    "collect_training_metrics.py",
    "generate_insights.py",
    "refresh_quicksight.py",
    "finalize_results.py"
)

Write-Host "Packaging Lambda handlers..." -ForegroundColor Cyan
foreach ($file in $lambdaFiles) {
    $sourcePath = Join-Path $repoRoot "infra\lambda\functions\$file"
    if (-not (Test-Path $sourcePath)) {
        throw "Missing Lambda source file: $sourcePath"
    }

    $name = [System.IO.Path]::GetFileNameWithoutExtension($file)
    $stageDir = Join-Path $artifactDir $name
    New-Item -Path $stageDir -ItemType Directory | Out-Null
    Copy-Item -Path $sourcePath -Destination (Join-Path $stageDir "index.py")

    $zipPath = Join-Path $artifactDir "$name.zip"
    Compress-Archive -Path (Join-Path $stageDir "index.py") -DestinationPath $zipPath -Force

    $s3Key = "$Prefix/lambda/$name.zip"
    aws s3 cp $zipPath "s3://$BucketName/$s3Key" --region $Region | Out-Null
    Write-Host "Uploaded $name -> s3://$BucketName/$s3Key" -ForegroundColor Green
}

Write-Host "Packaging SageMaker training code..." -ForegroundColor Cyan
$trainingSource = Join-Path $repoRoot "infra\sagemaker\training\train_model.py"
$trainingTar = Join-Path $artifactDir "train_model.tar.gz"
tar -czf $trainingTar -C (Split-Path $trainingSource) (Split-Path $trainingSource -Leaf)
$trainingS3Key = "$Prefix/sagemaker/train_model.tar.gz"
aws s3 cp $trainingTar "s3://$BucketName/$trainingS3Key" --region $Region | Out-Null
Write-Host "Uploaded SageMaker script archive -> s3://$BucketName/$trainingS3Key" -ForegroundColor Green

Write-Host ""
Write-Host "Artifacts uploaded successfully." -ForegroundColor Green
Write-Host "Use this value in Step Functions placeholder REPLACE_SAGEMAKER_CODE_TAR_S3_URI:" -ForegroundColor Yellow
Write-Host "s3://$BucketName/$trainingS3Key" -ForegroundColor Yellow
