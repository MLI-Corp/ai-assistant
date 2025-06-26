<#
.SYNOPSIS
    Sets up the OpenWebUI Integrated Invoicing Assistant project on a Windows Server.
    This script guides through Docker and Git checks, clones the project,
    sets up initial configuration files, and starts the application using Docker Compose.

.DESCRIPTION
    The script performs the following actions:
    1. Checks for Docker Engine and Git. Provides guidance if not found.
    2. Prompts for the project's Git repository URL and a local directory for cloning.
    3. Clones the project.
    4. Creates initial .env files from templates.
    5. Creates a placeholder for client_billing_rates.json.
    6. Runs 'docker-compose pull' and 'docker-compose up -d --build'.
    7. Displays post-setup information and management commands.

    Note: This script should be run with Administrator privileges if Docker installation
    or certain Docker operations require it. Manual intervention is required to edit
    configuration files (.env, .env.assistant, client_billing_rates.json).

.VERSION
    1.0.0

.AUTHOR
    AI Assistant (Jules)

.EXAMPLE
    .\setup-windows-server.ps1
    Follow the prompts.

.NOTES
    Requires PowerShell 5.1 or higher.
    Ensure PowerShell execution policy allows running local scripts (e.g., Set-ExecutionPolicy RemoteSigned).
#>

#Requires -RunAsAdministrator # Uncomment if script needs to perform actions requiring admin by default.
# For Docker installation, admin is definitely needed. For just running docker-compose, maybe not always.

# --- Configuration ---
$DefaultRepoUrl = "https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git" # TODO: Replace with actual or leave as placeholder
$DefaultCloneParentDir = "$env:SystemDrive\projects"
$ProjectDirName = "InvoiceAssistant" # This will be the folder name inside CloneParentDir

# --- Helper Functions ---

function Test-CommandExists {
    param (
        [string]$CommandName
    )
    return (Get-Command $CommandName -ErrorAction SilentlyContinue) -ne $null
}

function Get-UserConfirmation {
    param (
        [string]$Message,
        [string]$Default = "N"
    )
    $validResponses = @("Y", "N")
    $choice = $Default
    while ($true) {
        try {
            $response = Read-Host -Prompt "$Message (Y/N, default '$Default')"
            if ([string]::IsNullOrWhiteSpace($response)) {
                $response = $Default
            }
            if ($validResponses -contains $response.ToUpper()) {
                return $response.ToUpper() -eq "Y"
            }
            Write-Warning "Invalid input. Please enter Y or N."
        }
        catch {
            Write-Warning "Error reading input. Please try again."
        }
    }
}

function Show-DockerInstallInstructions {
    Write-Host "----------------------------------------" -ForegroundColor Yellow
    Write-Host "Docker Engine Installation (Windows Server)" -ForegroundColor Yellow
    Write-Host "----------------------------------------" -ForegroundColor Yellow
    Write-Host "Docker is not detected or not working correctly."
    Write-Host "To install Docker Engine on Windows Server (No GUI), you typically need to:"
    Write-Host "1. Ensure your Windows Server version supports Docker and Hyper-V (if using Hyper-V backend)."
    Write-Host "2. Open PowerShell as Administrator."
    Write-Host "3. Enable the 'Containers' and 'Hyper-V' Windows features (Hyper-V might be optional for Windows containers but often used):"
    Write-Host "   Install-WindowsFeature -Name Containers, Hyper-V -IncludeAllSubFeature -IncludeManagementTools -Restart"
    Write-Host "   (A restart will be required after installing features)."
    Write-Host ""
    Write-Host "4. Install the Docker Microsoft Provider module:"
    Write-Host "   Install-Module -Name DockerMsftProvider -Repository PSGallery -Force"
    Write-Host ""
    Write-Host "5. Install Docker Package:"
    Write-Host "   Install-Package -Name docker -ProviderName DockerMsftProvider -Force"
    Write-Host ""
    Write-Host "6. Restart the Docker service (or the server if prompted):"
    Write-Host "   Restart-Service docker"
    Write-Host ""
    Write-Host "7. Test Docker installation:"
    Write-Host "   docker --version"
    Write-Host "   docker run hello-world (this will download and run a test image)"
    Write-Host ""
    Write-Host "For official and detailed instructions, please refer to:"
    Write-Host "- Microsoft Docs: https://docs.microsoft.com/en-us/virtualization/windowscontainers/quick-start/set-up-environment?tabs=Windows-Server"
    Write-Host "----------------------------------------" -ForegroundColor Yellow
    Write-Host "Please install Docker and ensure it's running, then re-run this script." -ForegroundColor Cyan
    Write-Host "Script will now exit."
    exit 1
}

function Show-GitInstallInstructions {
    Write-Host "----------------------------------------" -ForegroundColor Yellow
    Write-Host "Git Installation" -ForegroundColor Yellow
    Write-Host "----------------------------------------" -ForegroundColor Yellow
    Write-Host "Git is not detected on your system or not in PATH."
    Write-Host "Please download and install Git for Windows from: https://git-scm.com/download/win"
    Write-Host "During installation, ensure you select an option that adds Git to your PATH."
    Write-Host "(e.g., 'Git from the command line and also from 3rd-party software')."
    Write-Host "After installation, please open a new PowerShell window and re-run this script."
    Write-Host "----------------------------------------" -ForegroundColor Yellow
    Write-Host "Script will now exit."
    exit 1
}

# --- Main Script Logic ---

Write-Host "Starting setup for OpenWebUI Integrated Invoicing Assistant..." -ForegroundColor Green

# 1. Check for Docker
Write-Host "`n--- Checking for Docker ---" -ForegroundColor Cyan
if (-not (Test-CommandExists -CommandName "docker")) {
    Show-DockerInstallInstructions
}
# Try a simple docker command to see if daemon is running
docker ps -q > $null
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Docker command 'docker ps' failed. The Docker daemon might not be running or accessible."
    Show-DockerInstallInstructions # Show full instructions again as it's crucial
}
Write-Host "Docker appears to be installed and accessible." -ForegroundColor Green

# 2. Check for Git
Write-Host "`n--- Checking for Git ---" -ForegroundColor Cyan
if (-not (Test-CommandExists -CommandName "git")) {
    Show-GitInstallInstructions
}
Write-Host "Git appears to be installed." -ForegroundColor Green

# 3. Project Cloning
Write-Host "`n--- Project Cloning ---" -ForegroundColor Cyan
$RepoUrl = Read-Host -Prompt "Enter Git repository URL for the project (default: $DefaultRepoUrl)"
if ([string]::IsNullOrWhiteSpace($RepoUrl)) { $RepoUrl = $DefaultRepoUrl }

$CloneParentDir = Read-Host -Prompt "Enter parent directory to clone project into (default: $DefaultCloneParentDir)"
if ([string]::IsNullOrWhiteSpace($CloneParentDir)) { $CloneParentDir = $DefaultCloneParentDir }

$FullProjectPath = Join-Path -Path $CloneParentDir -ChildPath $ProjectDirName

if (-not (Test-Path -Path $CloneParentDir -PathType Container)) {
    Write-Host "Parent directory '$CloneParentDir' does not exist. Attempting to create it..."
    try {
        New-Item -ItemType Directory -Path $CloneParentDir -Force -ErrorAction Stop | Out-Null
        Write-Host "Parent directory '$CloneParentDir' created." -ForegroundColor Green
    }
    catch {
        Write-Error "Failed to create parent directory '$CloneParentDir'. Please create it manually and re-run. Error: $($_.Exception.Message)"
        exit 1
    }
}

if (Test-Path -Path $FullProjectPath -PathType Container) {
    Write-Warning "Project directory '$FullProjectPath' already exists."
    if (-not (Get-UserConfirmation -Message "Do you want to attempt to update (git pull) and use existing directory?" -Default "Y")) {
        Write-Host "Exiting script. Please remove or rename the existing directory, or choose a different location."
        exit 1
    }
    Set-Location -Path $FullProjectPath -ErrorAction Stop
    Write-Host "Attempting to update existing project in '$FullProjectPath'..."
    git pull
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "git pull failed. Continuing with existing local version. Please check for errors manually if needed."
    }
} else {
    Write-Host "Cloning project from '$RepoUrl' into '$FullProjectPath'..."
    git clone $RepoUrl $FullProjectPath
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to clone repository from '$RepoUrl'. Please check the URL and your network connection."
        exit 1
    }
    Set-Location -Path $FullProjectPath -ErrorAction Stop
    Write-Host "Project cloned successfully." -ForegroundColor Green
}

# 4. Environment File Setup
Write-Host "`n--- Setting up Environment Files ---" -ForegroundColor Cyan
$EnvTemplate = ".env.template"
$EnvFile = ".env"
if (Test-Path $EnvTemplate) {
    if (-not (Test-Path $EnvFile)) {
        Copy-Item $EnvTemplate $EnvFile -Force
        Write-Host "Copied '$EnvTemplate' to '$EnvFile'."
    } else {
        Write-Host "'$EnvFile' already exists. Skipping copy."
    }
} else {
    Write-Warning "'$EnvTemplate' not found in project root."
}

$AssistantEnvTemplate = "backend_assistant\.env.assistant.template" # Path relative to project root
$AssistantEnvFile = "backend_assistant\.env.assistant"
if (Test-Path $AssistantEnvTemplate) {
    if (-not (Test-Path $AssistantEnvFile)) {
        Copy-Item $AssistantEnvTemplate $AssistantEnvFile -Force
        Write-Host "Copied '$AssistantEnvTemplate' to '$AssistantEnvFile'."
    } else {
        Write-Host "'$AssistantEnvFile' already exists. Skipping copy."
    }
} else {
    Write-Warning "'$AssistantEnvTemplate' not found."
}
Write-Host "IMPORTANT: Please manually edit '$EnvFile' (if created) and '$AssistantEnvFile' with your specific configurations (API keys, credentials, etc.) before proceeding if this is the first setup." -ForegroundColor Yellow
if (-not (Get-UserConfirmation -Message "Have you configured the .env files (if this is not your first run, they might be okay)? Or are you ready to proceed with defaults/existing?" -Default "N")) {
    Write-Host "Please configure the .env files and then re-run the script, or choose to proceed if you are sure."
    Write-Host "You can typically proceed if you are just updating the application via git pull and docker-compose build."
    # exit 1 # Make this optional if user wants to proceed with possibly unconfigured .env files for a test
}


# 5. Client Billing Rates Placeholder
Write-Host "`n--- Setting up Client Billing Rates Placeholder ---" -ForegroundColor Cyan
$RatesDir = "backend_assistant\config"
$RatesFile = Join-Path -Path $RatesDir -ChildPath "client_billing_rates.json"
if (-not (Test-Path -Path $RatesDir -PathType Container)) {
    New-Item -ItemType Directory -Path $RatesDir -Force | Out-Null
}
if (-not (Test-Path -Path $RatesFile)) {
    Set-Content -Path $RatesFile -Value "{}"
    Write-Host "Created placeholder '$RatesFile'. Please configure it as per backend_assistant/README.md." -ForegroundColor Yellow
} else {
    Write-Host "'$RatesFile' already exists."
}

# 6. Docker Compose Operations
Write-Host "`n--- Docker Compose Operations ---" -ForegroundColor Cyan
Write-Host "Pulling latest base images for services (this might take a while)..."
docker-compose pull
if ($LASTEXITCODE -ne 0) {
    Write-Warning "docker-compose pull encountered issues. Some services might use older base images if already present locally."
    # Optionally, make this a hard stop:
    # Write-Error "docker-compose pull failed. Cannot proceed."
    # exit 1
} else {
    Write-Host "docker-compose pull completed." -ForegroundColor Green
}

Write-Host "`nBuilding and starting services with 'docker-compose up -d --build' (this might take a while)..."
docker-compose up -d --build
if ($LASTEXITCODE -ne 0) {
    Write-Error "docker-compose up -d --build failed. Please check the output for errors."
    Write-Host "You can try running 'docker-compose logs -f backend_assistant' (and other services) to see specific errors."
    exit 1
}
Write-Host "Docker services started successfully." -ForegroundColor Green

# 7. Post-Setup Information
Write-Host "`n--- Setup Complete ---" -ForegroundColor Green
Write-Host "The OpenWebUI Integrated Invoicing Assistant should now be running."
Write-Host "Access Services:"
Write-Host "  - InvoiceNinja UI:           http://localhost:9000"
Write-Host "  - OpenWebUI:                 http://localhost:3000"
Write-Host "  - Backend Assistant API Docs:  http://localhost:8001/docs"
Write-Host "  - Backend Assistant Health:  http://localhost:8001/health"
Write-Host "  - Backend Assistant WebSocket: ws://localhost:8001/ws/status"
Write-Host ""
Write-Host "Common Management Commands (run from '$FullProjectPath'):"
Write-Host "  - View logs for all services:      docker-compose logs -f"
Write-Host "  - View assistant logs:             docker-compose logs -f backend_assistant"
Write-Host "  - Stop all services:               docker-compose stop"
Write-Host "  - Stop and remove containers:      docker-compose down"
Write-Host "  - Stop, remove containers & vols:  docker-compose down -v (USE WITH CAUTION - DELETES DATA)"
Write-Host ""
Write-Host "Remember to check and configure:"
Write-Host "  - '$EnvFile' (if created/modified)"
Write-Host "  - '$AssistantEnvFile'"
Write-Host "  - '$RatesFile'"
Write-Host "  - Google OAuth Refresh Token setup as per backend_assistant/README.md if using Google Calendar."
Write-Host ""
Write-Host "Script finished." -ForegroundColor Green
```
